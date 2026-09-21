from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNoEncontrado
from app.models import AuditLog, Cliente, Cuenta, Cuota, MovimientoContable, Prestamo, Transaccion
from app.models.contabilidad import CODIGO_DEPOSITOS_VISTA, CODIGO_INGRESOS_INTERESES, CODIGO_PRESTAMOS_POR_COBRAR
from app.models.prestamo import bucket_de, fecha_vencimiento_de
from app.schemas.prestamos import CuotaOut, MontoConceptoOut, PrestamoOut, PrestamoRevisionOut, ProximaCuotaOut, SolicitudPrestamoIn
from app.services import comisiones as comisiones_service
from app.services.contabilidad import acreditar, cuenta_contable_id, debitar, registrar_asiento

# ponytail: regla de elegibilidad naive por segmento (limite de autoevaluacion, tasa);
# reemplazar por un modelo de riesgo real en la fase de GenAI/analitica del curso.
LIMITES_SEGMENTO: dict[str, tuple[Decimal, Decimal]] = {
    "joven": (Decimal("5000"), Decimal("22.00")),
    "clasico": (Decimal("15000"), Decimal("18.50")),
    "premium": (Decimal("50000"), Decimal("14.90")),
    "empresa": (Decimal("100000"), Decimal("16.00")),
}


class PrestamoYaResuelto(Exception):
    pass


class RequiereAdmin(Exception):
    """V13: un caso de un cliente marcado es_empleado (conflicto de interes) solo lo resuelve un admin."""


class PrestamoNoVigente(Exception):
    pass


def generar_cronograma(monto: Decimal, tasa: Decimal, plazo: int, fecha_desembolso: date) -> list[dict]:
    """Sistema frances, cuota fija (HU-Ciclo-Vida-Prestamo). Pura -sin DB-, testeable directo
    con el vector de la HU. Invariante: sum(capital) == monto exacto (la ultima cuota absorbe
    el redondeo de las anteriores)."""
    with localcontext() as ctx:
        ctx.prec = 40
        tem = (Decimal(1) + tasa / Decimal(100)) ** (Decimal(1) / Decimal(12)) - Decimal(1)
        if tem == 0:
            cuota = (monto / plazo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            cuota = (monto * tem / (Decimal(1) - (Decimal(1) + tem) ** Decimal(-plazo))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        filas = []
        saldo = monto
        for k in range(1, plazo + 1):
            interes_k = (saldo * tem).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            capital_k = saldo if k == plazo else (cuota - interes_k)
            total_k = capital_k + interes_k
            saldo = saldo - capital_k
            filas.append({
                "numero": k, "fecha_vencimiento": fecha_vencimiento_de(fecha_desembolso, k),
                "capital": capital_k, "interes": interes_k, "total": total_k,
                "saldo_capital_despues": saldo, "estado": "pendiente",
            })
        return filas


def desembolsar(db: Session, prestamo: Prestamo, cuenta: Cuenta) -> None:
    """V2: desembolso + transaccion + asiento + cronograma en la misma transaccion SQL que
    quien llama (no hace su propio commit; solicitar()/resolver() lo hacen)."""
    hoy = date.today()
    prestamo.fecha_desembolso = hoy

    acreditar(db, cuenta.cuenta_id, prestamo.monto_original)

    transaccion = Transaccion(
        cuenta_destino_id=cuenta.cuenta_id, tipo="desembolso", monto=prestamo.monto_original,
        canal="sistema", estado="aplicada", concepto=f"Desembolso de préstamo #{prestamo.prestamo_id}",
    )
    db.add(transaccion)
    db.flush()

    prestamos_id = cuenta_contable_id(db, CODIGO_PRESTAMOS_POR_COBRAR)
    depositos_id = cuenta_contable_id(db, CODIGO_DEPOSITOS_VISTA)
    movs = [
        MovimientoContable(cuenta_contable_id=prestamos_id, cuenta_cliente_id=None,
                            tipo_movimiento="D", importe=prestamo.monto_original, moneda=cuenta.moneda),
        MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta.cuenta_id,
                            tipo_movimiento="H", importe=prestamo.monto_original, moneda=cuenta.moneda),
    ]
    registrar_asiento(db, "desembolso", transaccion.transaccion_id, movs)

    filas = generar_cronograma(prestamo.monto_original, prestamo.tasa, prestamo.plazo, hoy)
    db.add_all([Cuota(prestamo_id=prestamo.prestamo_id, **fila) for fila in filas])


def a_schema(p: Prestamo) -> PrestamoOut:
    cuotas = sorted(p.cuotas, key=lambda c: c.numero)
    cuotas_pagadas = sum(1 for c in cuotas if c.estado == "pagada")
    proxima = next((c for c in cuotas if c.estado in ("pendiente", "vencida")), None)
    return PrestamoOut(
        prestamo_id=p.prestamo_id, monto_original=p.monto_original, saldo_capital=p.saldo_capital, tasa=p.tasa,
        plazo=p.plazo, fecha_desembolso=p.fecha_desembolso,
        fecha_vencimiento=fecha_vencimiento_de(p.fecha_desembolso, p.plazo) if p.fecha_desembolso else None,
        dias_mora=p.dias_mora, bucket_mora=p.bucket_mora, estado=p.estado,
        cuenta_desembolso_numero=p.cuenta_desembolso.numero_cuenta if p.cuenta_desembolso else None,
        cuotas_total=len(cuotas), cuotas_pagadas=cuotas_pagadas,
        proxima_cuota=ProximaCuotaOut(numero=proxima.numero, fecha_vencimiento=proxima.fecha_vencimiento,
                                       total=proxima.total, estado=proxima.estado) if proxima else None,
    )


def solicitar(db: Session, cliente_id: int, usuario_id: int, datos: SolicitudPrestamoIn, ip: str | None = None) -> Prestamo:
    """RF-06: hibrido. Monto grande -> revision humana en backoffice (como un banco real).
    Monto dentro del limite del segmento -> decision automatica instantanea, con desembolso."""
    cuenta = db.scalar(select(Cuenta).where(Cuenta.cuenta_id == datos.cuenta_id, Cuenta.cliente_id == cliente_id))
    if cuenta is None or cuenta.estado != "activa" or cuenta.moneda != "PEN":
        raise RecursoNoEncontrado()

    segmento = db.scalar(select(Cliente.segmento).where(Cliente.cliente_id == cliente_id))
    limite, tasa = LIMITES_SEGMENTO[segmento]

    if datos.monto_original > limite:
        estado = "solicitado"
    else:
        tiene_mora_vigente = db.scalar(
            select(Prestamo.prestamo_id).where(
                Prestamo.cliente_id == cliente_id, Prestamo.estado == "vigente", Prestamo.dias_mora > 0
            )
        ) is not None
        estado = "rechazado" if tiene_mora_vigente else "vigente"

    prestamo = Prestamo(
        cliente_id=cliente_id, cuenta_desembolso_id=cuenta.cuenta_id,
        monto_original=datos.monto_original, saldo_capital=datos.monto_original,
        tasa=tasa, plazo=datos.plazo, dias_mora=0, bucket_mora="0", estado=estado,
    )
    db.add(prestamo)
    db.flush()

    if estado == "vigente":
        desembolsar(db, prestamo, cuenta)

    db.add(AuditLog(usuario_id=usuario_id, accion="crear", entidad="prestamo", entidad_id=str(prestamo.prestamo_id), ip=ip))
    db.commit()
    db.refresh(prestamo)
    return prestamo


def listar(db: Session, cliente_id: int) -> list[Prestamo]:
    return list(db.scalars(
        select(Prestamo).where(Prestamo.cliente_id == cliente_id).order_by(Prestamo.prestamo_id.desc())
    ))


def obtener_propio(db: Session, cliente_id: int, prestamo_id: int) -> Prestamo:
    prestamo = db.scalar(select(Prestamo).where(Prestamo.prestamo_id == prestamo_id, Prestamo.cliente_id == cliente_id))
    if prestamo is None:
        raise RecursoNoEncontrado()
    return prestamo


def cronograma(db: Session, cliente_id: int, prestamo_id: int) -> list[CuotaOut]:
    prestamo = obtener_propio(db, cliente_id, prestamo_id)
    cuotas = sorted(prestamo.cuotas, key=lambda c: c.numero)
    return [CuotaOut.model_validate(c) for c in cuotas]


def recalcular_mora(db: Session, prestamo: Prestamo, fecha_referencia: date) -> None:
    """V7: solo cierre_diario y el pago (regularizacion) escriben dias_mora/bucket_mora."""
    vencida_mas_antigua = db.scalar(
        select(func.min(Cuota.fecha_vencimiento)).where(Cuota.prestamo_id == prestamo.prestamo_id, Cuota.estado == "vencida")
    )
    prestamo.dias_mora = 0 if vencida_mas_antigua is None else (fecha_referencia - vencida_mas_antigua).days
    prestamo.bucket_mora = bucket_de(prestamo.dias_mora)


def pagar_cuota(db: Session, prestamo_id: int, cliente_id: int, usuario_id: int, cuenta_origen_id: int, ip: str | None = None) -> dict:
    """V3: siempre la cuota impaga mas antigua, por su total exacto (mas PRE-ATR si vencida).
    V4: guardia atomica; si el saldo no alcanza, nada cambia. Todo en un commit."""
    prestamo = db.scalar(select(Prestamo).where(Prestamo.prestamo_id == prestamo_id, Prestamo.cliente_id == cliente_id))
    if prestamo is None:
        raise RecursoNoEncontrado()
    if prestamo.estado != "vigente":
        raise PrestamoNoVigente()

    cuota = db.scalar(
        select(Cuota).where(Cuota.prestamo_id == prestamo_id, Cuota.estado.in_(("pendiente", "vencida")))
        .order_by(Cuota.numero).limit(1)
    )
    if cuota is None:
        raise PrestamoNoVigente()  # defensa: no deberia ocurrir si estado == vigente

    cuenta = db.scalar(select(Cuenta).where(
        Cuenta.cuenta_id == cuenta_origen_id, Cuenta.cliente_id == cliente_id, Cuenta.estado == "activa",
    ))
    if cuenta is None:
        raise RecursoNoEncontrado()

    hoy = date.today()
    era_vencida = cuota.estado == "vencida"

    debitar(db, cuenta.cuenta_id, cuota.total)

    transaccion = Transaccion(
        cuenta_origen_id=cuenta.cuenta_id, tipo="pago_prestamo", monto=cuota.total, canal="web",
        estado="aplicada", concepto=f"Pago cuota {cuota.numero}/{prestamo.plazo}",
    )
    db.add(transaccion)
    db.flush()

    depositos_id = cuenta_contable_id(db, CODIGO_DEPOSITOS_VISTA)
    prestamos_id = cuenta_contable_id(db, CODIGO_PRESTAMOS_POR_COBRAR)
    intereses_id = cuenta_contable_id(db, CODIGO_INGRESOS_INTERESES)
    movs = [
        MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta.cuenta_id,
                            tipo_movimiento="D", importe=cuota.total, moneda=cuenta.moneda),
        MovimientoContable(cuenta_contable_id=prestamos_id, cuenta_cliente_id=None,
                            tipo_movimiento="H", importe=cuota.capital, moneda=cuenta.moneda),
        MovimientoContable(cuenta_contable_id=intereses_id, cuenta_cliente_id=None,
                            tipo_movimiento="H", importe=cuota.interes, moneda=cuenta.moneda),
    ]
    registrar_asiento(db, "pago_prestamo", transaccion.transaccion_id, movs)

    cuota.estado = "pagada"
    cuota.fecha_pago = hoy
    cuota.transaccion_id = transaccion.transaccion_id
    prestamo.saldo_capital -= cuota.capital

    penalidad = None
    if era_vencida:
        dias_atraso = (hoy - cuota.fecha_vencimiento).days
        tarifa, monto_penalidad = comisiones_service.calcular(db, "pago_cuota_vencida", cuenta.cuenta_id, hoy)
        if monto_penalidad > 0:
            concepto = f"Penalidad: cuota {cuota.numero} atrasada {dias_atraso} días"
            mensaje_error = f"Saldo insuficiente para la cuota más la penalidad de S/ {tarifa.monto:.2f}"
            comisiones_service.cobrar(db, tarifa, cuenta.cuenta_id, cuenta.moneda, transaccion.transaccion_id, concepto, mensaje_error)
            penalidad = {"monto": monto_penalidad, "concepto": concepto}

    recalcular_mora(db, prestamo, hoy)

    quedan_impagas = db.scalar(
        select(Cuota.cuota_id).where(Cuota.prestamo_id == prestamo_id, Cuota.estado.in_(("pendiente", "vencida")))
    ) is not None
    if not quedan_impagas:
        prestamo.estado = "cancelado"

    db.add(AuditLog(usuario_id=usuario_id, accion="pagar_cuota", entidad="cuota", entidad_id=str(cuota.cuota_id), ip=ip))
    db.commit()
    db.refresh(cuota)
    db.refresh(prestamo)

    total_debitado = cuota.total + (penalidad["monto"] if penalidad else Decimal("0.00"))
    return {
        "cuota": CuotaOut.model_validate(cuota),
        "transaccion_id": transaccion.transaccion_id,
        "penalidad": MontoConceptoOut(**penalidad) if penalidad else None,
        "total_debitado": total_debitado,
        "saldo_capital": prestamo.saldo_capital,
        "estado_prestamo": prestamo.estado,
    }


def listar_pendientes(db: Session) -> list[PrestamoRevisionOut]:
    filas = db.execute(
        select(Prestamo, Cliente)
        .join(Cliente, Prestamo.cliente_id == Cliente.cliente_id)
        .where(Prestamo.estado == "solicitado")
        .order_by(Prestamo.prestamo_id)
    ).all()
    return [
        PrestamoRevisionOut(
            **a_schema(p).model_dump(), cliente_id=c.cliente_id,
            cliente_nombre=f"{c.nombres} {c.apellidos}", cliente_documento=c.numero_documento,
        )
        for p, c in filas
    ]


def resolver(db: Session, prestamo_id: int, decision: str, usuario_id: int, rol: str, ip: str | None = None) -> Prestamo:
    prestamo = db.get(Prestamo, prestamo_id)
    if prestamo is None:
        raise RecursoNoEncontrado()
    if prestamo.estado != "solicitado":
        raise PrestamoYaResuelto()

    cliente = db.get(Cliente, prestamo.cliente_id)
    if cliente.es_empleado and rol != "admin":
        raise RequiereAdmin()

    if decision == "aprobar":
        prestamo.estado = "vigente"
        desembolsar(db, prestamo, prestamo.cuenta_desembolso)
    else:
        prestamo.estado = "rechazado"

    db.flush()
    # sin columna revisado_por en Prestamo (a diferencia de Queja) — el audit log ya cubre quien/cuando.
    db.add(AuditLog(usuario_id=usuario_id, accion=f"{decision}_prestamo", entidad="prestamo",
                     entidad_id=str(prestamo_id), ip=ip))
    db.commit()
    db.refresh(prestamo)
    return prestamo
