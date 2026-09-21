from decimal import Decimal

from sqlalchemy import insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AsientoDesbalanceado, RecursoNoEncontrado, SaldoInsuficiente
from app.models import AsientoContable, AuditLog, Cuenta, MovimientoContable, Transaccion
from app.models.contabilidad import CODIGO_CAJA, CODIGO_DEPOSITOS_VISTA, CuentaContable
from app.schemas.transacciones import TransaccionIn


class MonedaIncompatible(Exception):
    pass


def _debitar(db: Session, cuenta_id: int, monto: Decimal) -> None:
    # ponytail: guardia atomica a nivel de fila (UPDATE ... WHERE saldo >= monto); el motor
    # serializa updates concurrentes sobre la misma fila, no hace falta un lock explicito.
    # La resta ocurre en DECIMAL nativo de SQL Server, nunca en Python/float.
    resultado = db.execute(
        update(Cuenta).where(Cuenta.cuenta_id == cuenta_id, Cuenta.saldo >= monto).values(saldo=Cuenta.saldo - monto)
    )
    if resultado.rowcount == 0:
        raise SaldoInsuficiente()


def _acreditar(db: Session, cuenta_id: int, monto: Decimal) -> None:
    db.execute(update(Cuenta).where(Cuenta.cuenta_id == cuenta_id).values(saldo=Cuenta.saldo + monto))


def verificar_balance(movimientos: list[MovimientoContable]) -> None:
    """Pura: Sigma DEBE debe ser igual a Sigma HABER. Separada de _registrar_asiento_partida_doble
    para poder probarla directo con un asiento armado a mano (defensa en profundidad, V6)."""
    suma_debe = sum(m.importe for m in movimientos if m.tipo_movimiento == "D")
    suma_haber = sum(m.importe for m in movimientos if m.tipo_movimiento == "H")
    if suma_debe != suma_haber:
        raise AsientoDesbalanceado()


def _cuenta_contable_id(db: Session, codigo: str) -> int:
    id_ = db.scalar(select(CuentaContable.cuenta_contable_id).where(CuentaContable.codigo == codigo))
    if id_ is None:
        raise RuntimeError(f"Plan de cuentas incompleto: falta el codigo {codigo!r} (ver seed en la migracion)")
    return id_


def _registrar_asiento_partida_doble(
    db: Session, tipo_operacion: str, transaccion_id: int, monto: Decimal, moneda: str,
    cuenta_cliente_debe: int | None, cuenta_cliente_haber: int | None,
) -> AsientoContable:
    """Arma el asiento segun la operacion. La convencion contable es fija por tipo:
    deposito       -> DEBE Caja                 / HABER Depositos a la vista (cliente destino)
    retiro         -> DEBE Depositos a la vista (cliente origen) / HABER Caja
    transferencia  -> DEBE Depositos a la vista (origen) / HABER Depositos a la vista (destino)
    Nunca toca `transaccion` (la FK vive en asiento_contable.transaccion_id, ver §3.2 del doc)."""
    caja_id = None
    depositos_id = None
    if tipo_operacion in ("deposito", "retiro"):
        caja_id = _cuenta_contable_id(db, CODIGO_CAJA)
    if cuenta_cliente_debe is not None or cuenta_cliente_haber is not None:
        depositos_id = _cuenta_contable_id(db, CODIGO_DEPOSITOS_VISTA)

    if tipo_operacion == "deposito":
        movs = [
            MovimientoContable(cuenta_contable_id=caja_id, cuenta_cliente_id=None,
                                tipo_movimiento="D", importe=monto, moneda=moneda),
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_haber,
                                tipo_movimiento="H", importe=monto, moneda=moneda),
        ]
    elif tipo_operacion == "retiro":
        movs = [
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_debe,
                                tipo_movimiento="D", importe=monto, moneda=moneda),
            MovimientoContable(cuenta_contable_id=caja_id, cuenta_cliente_id=None,
                                tipo_movimiento="H", importe=monto, moneda=moneda),
        ]
    else:  # transferencia
        movs = [
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_debe,
                                tipo_movimiento="D", importe=monto, moneda=moneda),
            MovimientoContable(cuenta_contable_id=depositos_id, cuenta_cliente_id=cuenta_cliente_haber,
                                tipo_movimiento="H", importe=monto, moneda=moneda),
        ]

    verificar_balance(movs)  # V6: en codigo, ademas del trigger SQL trg_asiento_balanceado (defensa en profundidad)

    asiento = AsientoContable(tipo_operacion=tipo_operacion, transaccion_id=transaccion_id, estado="contabilizado")
    db.add(asiento)
    db.flush()  # asiento_contable no tiene trigger: el OUTPUT normal de SQLAlchemy funciona aqui.

    # ponytail: Core insert().values([...]) con las filas ya "horneadas" en el statement (no como
    # parametros de .execute()) a proposito. movimiento_contable SI tiene trigger
    # (trg_asiento_balanceado) y SQL Server prohibe OUTPUT sin INTO en una tabla con triggers
    # habilitados; tanto el flush ORM normal como el "bulk insert" de execute(insert(Modelo), lista)
    # intentan traer el id generado vía OUTPUT por defecto. Esta forma compila un solo INSERT
    # multi-fila sin OUTPUT: el trigger ve las N filas del asiento juntas en `inserted`, y
    # SQLAlchemy sigue convirtiendo Decimal->tipo de columna igual que en cualquier insert ORM.
    db.execute(insert(MovimientoContable).values([
        {
            "asiento_id": asiento.asiento_id,
            "cuenta_contable_id": m.cuenta_contable_id,
            "cuenta_cliente_id": m.cuenta_cliente_id,
            "tipo_movimiento": m.tipo_movimiento,
            "importe": m.importe,
            "moneda": m.moneda,
        }
        for m in movs
    ]))
    return asiento


def _resolver_destino(db: Session, valor: str) -> Cuenta | None:
    """valor ya viene validado por Pydantic (14 = numero_cuenta, 20 = cci, DV correcto)."""
    return db.scalar(select(Cuenta).where(
        or_(Cuenta.numero_cuenta == valor, Cuenta.cci == valor), Cuenta.estado == "activa",
    ))


def crear(db: Session, cliente_id: int, usuario_id: int, datos: TransaccionIn, ip: str | None = None) -> Transaccion:
    """RF-08: deposito/retiro/transferencia. Atomico: si algo falla antes del commit, nada se persiste
    (ni el UPDATE de saldo, ni la transaccion, ni el asiento contable que la sustenta).
    Canal fijo 'web' — no es un campo que el usuario elija."""
    origen_id = destino_id = None

    if datos.tipo == "deposito":
        # el cliente solo deposita en cuentas propias: no basta con acertar el numero de otra persona
        destino = db.scalar(select(Cuenta).where(
            or_(Cuenta.numero_cuenta == datos.cuenta_destino, Cuenta.cci == datos.cuenta_destino),
            Cuenta.cliente_id == cliente_id,
        ))
        if destino is None:
            raise RecursoNoEncontrado()
        _acreditar(db, destino.cuenta_id, datos.monto)
        destino_id, moneda = destino.cuenta_id, destino.moneda

    elif datos.tipo == "retiro":
        origen = db.scalar(select(Cuenta).where(Cuenta.cuenta_id == datos.cuenta_origen_id, Cuenta.cliente_id == cliente_id))
        if origen is None:
            raise RecursoNoEncontrado()
        _debitar(db, origen.cuenta_id, datos.monto)
        origen_id, moneda = origen.cuenta_id, origen.moneda

    else:  # transferencia
        origen = db.scalar(select(Cuenta).where(Cuenta.cuenta_id == datos.cuenta_origen_id, Cuenta.cliente_id == cliente_id))
        destino = _resolver_destino(db, datos.cuenta_destino)
        if origen is None or destino is None:
            raise RecursoNoEncontrado()
        if origen.cuenta_id == destino.cuenta_id:
            raise RecursoNoEncontrado()  # transferirse a si mismo por CCI/numero propio: mismo mensaje, sin filtrar
        if origen.moneda != destino.moneda:
            # ponytail: sin fuente de tipo de cambio en esta app; se rechaza en vez de convertir.
            raise MonedaIncompatible()
        _debitar(db, origen.cuenta_id, datos.monto)
        _acreditar(db, destino.cuenta_id, datos.monto)
        origen_id, destino_id, moneda = origen.cuenta_id, destino.cuenta_id, origen.moneda

    transaccion = Transaccion(
        cuenta_origen_id=origen_id, cuenta_destino_id=destino_id,
        tipo=datos.tipo, monto=datos.monto, canal="web", estado="aplicada",
    )
    db.add(transaccion)
    db.flush()  # obtiene transaccion_id, igual que ya hacia el codigo para el AuditLog

    _registrar_asiento_partida_doble(
        db, datos.tipo, transaccion.transaccion_id, datos.monto, moneda,
        cuenta_cliente_debe=origen_id, cuenta_cliente_haber=destino_id,
    )
    db.add(AuditLog(usuario_id=usuario_id, accion="crear", entidad="transaccion",
                     entidad_id=str(transaccion.transaccion_id), ip=ip))
    db.commit()
    db.refresh(transaccion)
    return transaccion
