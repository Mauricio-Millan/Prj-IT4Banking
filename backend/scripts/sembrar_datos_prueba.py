"""Simula ~75 dias de actividad bancaria real, dia por dia, para tener datos de demo
distribuidos en el tiempo (no fabricados): 20 clientes personas naturales + 1 empresa,
depositos/retiros/transferencias, 8 solicitudes de prestamo con pagos de cuota (a tiempo,
tarde con PRE-ATR, o impagos), interes pasivo y comisiones reales via cierre_diario corrido
una vez por cada dia simulado, y unas quejas clasificadas.

HU-Gastos-Operativos-Intereses-Pasivos: cambio de arquitectura respecto a la version anterior
de este script (que generaba todo "hoy" y solo re-etiquetaba fecha_hora). cierre_diario debe
correr dia por dia para que mora/segmento/interes resulten de ejecutar la logica real
repetidamente -- no de un solo calculo final. Los servicios de prestamo/comision aceptan un
parametro `fecha` explicito (ver services/prestamos.py) para que el cronograma, los pagos y las
penalidades queden fechados en el dia simulado; depositos/retiros/transferencias siguen
usando el truco ya existente de re-etiquetar fecha_hora/fecha_contable despues del hecho
(_backdatar_transaccion), porque ahi no depende de nada mas que se calcule con esa fecha.

No es idempotente: usa DNIs y correos fijos, un segundo run choca con los UNIQUE existentes.
No es parte del reset de HU-Numeracion-Bancaria; es puramente para tener datos con los que
probar la app manualmente (pantallas de movimientos, backoffice, dashboards de Power BI, etc.).

Uso: python -m scripts.sembrar_datos_prueba [--dias N]  (default 75)
"""
import argparse
import os
import random
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ.setdefault("LLM_PROVIDER", "falso")  # cero llamadas de red reales al clasificar quejas

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from app.core.db import SessionLocal
from app.jobs import cierre_diario
from app.models import AsientoContable, Cliente, Cuenta, Cuota, Prestamo, Transaccion, Usuario
from app.schemas.auth import RegistroIn
from app.schemas.clientes_empresa import ClienteEmpresaIn
from app.schemas.prestamos import SolicitudPrestamoIn
from app.schemas.quejas import QuejaIn
from app.schemas.transacciones import TransaccionIn
from app.services import clientes_empresa as clientes_empresa_service
from app.services import onboarding
from app.services import prestamos as prestamos_service
from app.services import quejas as quejas_service
from app.services import transacciones as transacciones_service

random.seed(20260921)  # reproducible: mismo dataset si se necesita regenerar

NOMBRES = [
    ("Maria", "Quispe"), ("Jose", "Ramirez"), ("Ana", "Torres"), ("Luis", "Flores"),
    ("Rosa", "Mamani"), ("Carlos", "Huaman"), ("Carmen", "Vargas"), ("Jorge", "Rojas"),
    ("Lucia", "Chavez"), ("Pedro", "Salazar"), ("Elena", "Cruz"), ("Manuel", "Diaz"),
    ("Sofia", "Paredes"), ("Miguel", "Castillo"), ("Patricia", "Reyes"), ("Victor", "Gutierrez"),
    ("Gabriela", "Medina"), ("Ricardo", "Aguilar"), ("Diana", "Campos"), ("Fernando", "Vega"),
]
REGIONES = ("Lima", "Arequipa", "Cusco", "Piura", "La Libertad", "Junín", "Callao")
PASSWORD = "ClaveDePrueba1"

# indices (0-based) que se promueven a "premium" para variar los segmentos de prestamos
PREMIUM = {2, 5, 9, 13, 17}
# 8 clientes que reciben una solicitud de prestamo: (indice, monto, plazo)
SOLICITUDES_PRESTAMO = [
    (0, Decimal("3000.00"), 12),    # joven, dentro del limite -> vigente
    (1, Decimal("8000.00"), 24),    # joven, sobre el limite -> solicitado
    (3, Decimal("10000.00"), 18),   # clasico, dentro del limite -> vigente
    (4, Decimal("20000.00"), 36),   # clasico, sobre el limite -> solicitado
    (2, Decimal("30000.00"), 24),   # premium, dentro del limite -> vigente
    (5, Decimal("45000.00"), 48),   # premium, dentro del limite -> vigente
    (9, Decimal("60000.00"), 36),   # premium, sobre el limite -> solicitado
    (13, Decimal("15000.00"), 12),  # premium, dentro del limite -> vigente
]
# indices que reciben retiros extra por cajero/agente para cruzar la cuota gratis de RET-RED
CUENTAS_RETIRO_FRECUENTE = {6, 7, 8}

QUEJAS = [
    "No reconozco un cargo en mi cuenta, parece una transacción fraudulenta.",
    "El cobro de la comisión de mi tarjeta me parece excesivo este mes.",
    "La atención en la app fue muy lenta y no pude completar mi transferencia.",
    "Alguien clonó mi tarjeta y usó mi saldo sin autorización.",
    "Mi préstamo tiene un saldo distinto al que esperaba, revisen mi cuenta por favor.",
    "El cajero del centro comercial tardó demasiado en procesar mi retiro.",
    "Quiero saber por qué no me respondieron mi consulta anterior sobre mi cuenta.",
    "Sospecho de suplantación de identidad en un intento de acceso a mi cuenta.",
    "El canal de atención por chat no resolvió mi problema con la comisión cobrada.",
    "Necesito una aclaración sobre el interés que me cobraron en mi préstamo.",
]


def _backdatar_transaccion(db, transaccion: Transaccion, cuando: datetime) -> None:
    db.execute(update(Transaccion).where(Transaccion.transaccion_id == transaccion.transaccion_id).values(fecha_hora=cuando))
    db.execute(update(AsientoContable).where(AsientoContable.transaccion_id == transaccion.transaccion_id)
               .values(fecha_contable=cuando.date(), creado_en=cuando))
    db.commit()


def _con_reintentos(fn, intentos: int = 5, espera_segundos: int = 8):
    """La red hacia Azure SQL demostro ser inestable en corridas largas (75 dias secuenciales):
    dos corridas completas se cortaron por 'Error en el vinculo de comunicacion' a mitad de
    camino. Un dia que falla por un corte transitorio se reintenta entero en vez de abortar
    los 75 dias -- costaria volver a vaciar las tablas y empezar de cero otra vez."""
    for intento in range(1, intentos + 1):
        try:
            return fn()
        except OperationalError:
            if intento == intentos:
                raise
            print(f"    (conexion perdida, reintento {intento}/{intentos} en {espera_segundos}s...)")
            time.sleep(espera_segundos)


def _cargar_clientes_existentes(db) -> list[dict]:
    """--continuar: reconstruye la lista de clientes (mismo orden que _crear_clientes) desde
    filas ya sembradas, para reanudar sin recrearlos y sin chocar con los UNIQUE existentes."""
    filas = db.execute(
        select(Cliente.cliente_id, Usuario.usuario_id, Cuenta.cuenta_id, Cuenta.numero_cuenta)
        .join(Usuario, Usuario.cliente_id == Cliente.cliente_id)
        .join(Cuenta, Cuenta.cliente_id == Cliente.cliente_id)
        .where(Cliente.email.like("cliente%.prueba@correo.pe"))
        .order_by(Cliente.cliente_id)
    ).all()
    return [{"cliente_id": f[0], "usuario_id": f[1], "cuenta_id": f[2], "numero_cuenta": f[3]} for f in filas]


def _ultimo_cierre_corrido(db) -> date | None:
    from app.models import AuditLog
    fecha_str = db.scalar(
        select(AuditLog.entidad_id).where(AuditLog.accion == "cierre_diario").order_by(AuditLog.entidad_id.desc()).limit(1)
    )
    return date.fromisoformat(fecha_str) if fecha_str else None


def _saldo_actual(db, cuenta_id: int) -> Decimal:
    # select de la columna sola (no de la entidad Cuenta): evita leer un valor cacheado del
    # identity map, ya que SessionLocal usa expire_on_commit=False.
    return db.execute(select(Cuenta.saldo).where(Cuenta.cuenta_id == cuenta_id)).scalar()


def _crear_clientes(db) -> list[dict]:
    clientes = []
    for i, (nombres, apellidos) in enumerate(NOMBRES):
        edad_anios = random.randint(20, 55)
        fecha_nacimiento = date.today() - timedelta(days=edad_anios * 365 + random.randint(0, 364))
        datos = RegistroIn(
            tipo_documento="DNI", numero_documento=f"77{i:06d}", nombres=nombres, apellidos=apellidos,
            fecha_nacimiento=fecha_nacimiento, email=f"cliente{i + 1}.prueba@correo.pe",
            telefono=None, region=random.choice(REGIONES), password=PASSWORD,
        )
        cliente, usuario, cuenta, _tarjeta = onboarding.registrar(db, datos)
        clientes.append({"cliente_id": cliente.cliente_id, "usuario_id": usuario.usuario_id,
                          "cuenta_id": cuenta.cuenta_id, "numero_cuenta": cuenta.numero_cuenta})
        print(f"  cliente {i + 1}/20: {nombres} {apellidos} · {cuenta.numero_cuenta}")

    for idx in PREMIUM:
        db.execute(update(Cliente).where(Cliente.cliente_id == clientes[idx]["cliente_id"]).values(segmento="premium"))
    db.commit()
    print(f"{len(PREMIUM)} clientes promovidos a segmento premium: {sorted(PREMIUM)}")
    return clientes


def _crear_empresa(db, usuario_id_admin_ficticio: int) -> None:
    """Un cliente empresa (RUC), para que dim_cliente.es_empresa tenga al menos un caso real."""
    datos = ClienteEmpresaIn(
        ruc="20100070970", razon_social="Comercial Andina SAC", representante_nombres="Jorge",
        representante_apellidos="Salinas", email="representante.empresa@correo.pe", telefono=None, region="Lima",
    )
    resultado = clientes_empresa_service.crear(db, datos, usuario_id_admin_ficticio)
    print(f"  empresa: {datos.razon_social} · RUC {datos.ruc} · cuenta {resultado['cuenta'].numero_cuenta}")


def _depositar_inicial(db, clientes: list[dict], inicio: date) -> None:
    for c in clientes:
        monto = Decimal(random.randint(800, 4000))
        tx = transacciones_service.crear(
            db, c["cliente_id"], c["usuario_id"],
            TransaccionIn(tipo="deposito", monto=monto, cuenta_destino=c["numero_cuenta"], canal="agente"),
        )["transaccion"]
        cuando = datetime.combine(inicio, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=random.randint(0, 23))
        _backdatar_transaccion(db, tx, cuando)


def _solicitar_prestamos(db, clientes: list[dict], inicio: date) -> None:
    """fecha=inicio: el cronograma completo queda anclado al comienzo de la ventana simulada,
    para que las cuotas venzan DENTRO de esa ventana (si se solicitaran "hoy", vencerian en el
    futuro y la simulacion -que solo cubre el pasado- nunca llegaria a pagarlas)."""
    for idx, monto, plazo in SOLICITUDES_PRESTAMO:
        c = clientes[idx]
        p = prestamos_service.solicitar(
            db, c["cliente_id"], c["usuario_id"],
            SolicitudPrestamoIn(monto_original=monto, plazo=plazo, cuenta_id=c["cuenta_id"]),
            fecha=inicio,
        )
        print(f"  cliente {idx + 1} ({c['numero_cuenta']}): monto {monto} -> estado {p.estado}")


def _aplicar_transacciones_del_dia(db, clientes: list[dict], fecha_simulada: date) -> None:
    for i, c in enumerate(clientes):
        frecuente = i in CUENTAS_RETIRO_FRECUENTE
        # ~1 evento cada 3 dias por cliente normal; las cuentas de retiro frecuente casi a diario.
        if random.random() > (0.6 if frecuente else 0.33):
            continue

        saldo = _saldo_actual(db, c["cuenta_id"])
        if frecuente:
            tipo = "retiro"
        else:
            tipo = random.choices(["deposito", "retiro", "transferencia"], weights=[0.4, 0.3, 0.3])[0]
        if saldo < Decimal("20.00"):
            tipo = "deposito"

        try:
            if tipo == "deposito":
                monto = Decimal(random.randint(50, 1500))
                datos_tx = TransaccionIn(tipo="deposito", monto=monto, cuenta_destino=c["numero_cuenta"], canal="agente")
            elif tipo == "retiro":
                monto = Decimal(random.randint(20, 80)) if frecuente else (saldo * Decimal(random.randint(5, 35)) / 100).quantize(Decimal("0.01"))
                datos_tx = TransaccionIn(tipo="retiro", monto=max(monto, Decimal("10.00")), cuenta_origen_id=c["cuenta_id"], canal="cajero")
            else:
                destino = random.choice([o for o in clientes if o is not c])
                monto = (saldo * Decimal(random.randint(5, 35)) / 100).quantize(Decimal("0.01"))
                datos_tx = TransaccionIn(tipo="transferencia", monto=max(monto, Decimal("10.00")),
                                          cuenta_origen_id=c["cuenta_id"], cuenta_destino=destino["numero_cuenta"])
            tx = transacciones_service.crear(db, c["cliente_id"], c["usuario_id"], datos_tx)["transaccion"]
        except Exception:
            db.rollback()
            continue

        cuando = datetime.combine(fecha_simulada, datetime.min.time(), tzinfo=timezone.utc) + timedelta(
            hours=random.randint(0, 23), minutes=random.randint(0, 59))
        _backdatar_transaccion(db, tx, cuando)


def _aplicar_pagos_de_cuota_del_dia(db, clientes_por_id: dict, pagos_programados: dict, fecha_simulada: date) -> None:
    """Cada prestamo vigente decide, cuando su proxima cuota vence, si paga a tiempo (70%),
    tarde entre 5 y 20 dias (20%, genera PRE-ATR real) o no la paga en esta simulacion (10%)."""
    prestamos_vigentes = list(db.scalars(select(Prestamo).where(Prestamo.estado == "vigente")))
    for prestamo in prestamos_vigentes:
        proxima = db.scalar(
            select(Cuota).where(Cuota.prestamo_id == prestamo.prestamo_id, Cuota.estado.in_(("pendiente", "vencida")))
            .order_by(Cuota.numero).limit(1)
        )
        if proxima is None:
            continue

        objetivo = pagos_programados.get(prestamo.prestamo_id)
        # <=, no ==: cubre tanto el dia exacto de vencimiento como una cuota que ya estaba
        # vencida al reanudar con --continuar (pagos_programados se reconstruye vacio).
        if objetivo is None and proxima.fecha_vencimiento <= fecha_simulada:
            r = random.random()
            if r < 0.70:
                objetivo = fecha_simulada
            elif r < 0.90:
                objetivo = fecha_simulada + timedelta(days=random.randint(5, 20))
            else:
                objetivo = None  # nunca se paga en esta simulacion
            pagos_programados[prestamo.prestamo_id] = objetivo

        if objetivo == fecha_simulada:
            c = clientes_por_id[prestamo.cliente_id]
            try:
                prestamos_service.pagar_cuota(db, prestamo.prestamo_id, c["cliente_id"], c["usuario_id"],
                                               c["cuenta_id"], fecha=fecha_simulada)
            except Exception:
                db.rollback()
            pagos_programados.pop(prestamo.prestamo_id, None)


def _registrar_quejas(db, clientes: list[dict], dias_totales: int, inicio: date) -> None:
    usados = random.sample(range(len(clientes)), k=min(len(QUEJAS), len(clientes)))
    for texto, idx in zip(QUEJAS, usados):
        c = clientes[idx]
        queja = quejas_service.crear(db, c["cliente_id"], QuejaIn(texto=texto))
        dias = random.randint(0, dias_totales - 1)
        db.execute(update(type(queja)).where(type(queja).queja_id == queja.queja_id).values(
            creado_en=datetime.combine(inicio, datetime.min.time()) + timedelta(days=dias)))
        db.commit()
    print(f"{len(usados)} queja(s) registradas y clasificadas")


def _dia_completo(clientes: list[dict], clientes_por_id: dict, pagos_programados: dict, fecha_simulada: date) -> None:
    """Cuerpo de un dia simulado, envuelto entero en _con_reintentos: si un corte de red
    aborta a mitad de camino, se reintenta el dia completo (alguna transaccion de ese dia
    podria duplicarse en el peor caso -- aceptable para un dataset sintetico de demo, no para
    dinero real)."""
    db_dia = SessionLocal()
    try:
        _aplicar_transacciones_del_dia(db_dia, clientes, fecha_simulada)
        _aplicar_pagos_de_cuota_del_dia(db_dia, clientes_por_id, pagos_programados, fecha_simulada)
    finally:
        db_dia.close()
    cierre_diario.ejecutar(fecha_simulada)


def simular(dias_totales: int = 75, continuar: bool = False) -> None:
    db = SessionLocal()
    inicio = date.today() - timedelta(days=dias_totales)
    pagos_programados: dict[int, date | None] = {}

    if continuar:
        clientes = _cargar_clientes_existentes(db)
        if not clientes:
            raise SystemExit("--continuar pero no hay clientes sembrados todavia; corre sin --continuar primero")
        ultimo_cierre = _ultimo_cierre_corrido(db)
        # +1: ultimo_cierre ya termino y commiteo por completo (si no, no estaria en audit_log);
        # se retoma en el dia siguiente, nunca repitiendo uno ya cerrado.
        offset_inicial = (ultimo_cierre - inicio).days + 1 if ultimo_cierre else 0
        print(f"Reanudando: {len(clientes)} clientes existentes, ultimo cierre_diario corrido: {ultimo_cierre}")
        db.close()
    else:
        print(f"Simulando {dias_totales} dias: {inicio} -> {date.today() - timedelta(days=1)}\n")
        print("Creando clientes...")
        clientes = _crear_clientes(db)

        print("\nCreando cliente empresa...")
        _crear_empresa(db, usuario_id_admin_ficticio=clientes[0]["usuario_id"])

        print("\nDepositando saldo inicial...")
        _depositar_inicial(db, clientes, inicio)

        print("\nGenerando solicitudes de prestamo (ancladas al inicio de la ventana simulada)...")
        _solicitar_prestamos(db, clientes, inicio)

        print("\nRegistrando quejas...")
        _registrar_quejas(db, clientes, dias_totales, inicio)

        db.close()
        offset_inicial = 0

    clientes_por_id = {c["cliente_id"]: c for c in clientes}

    print("\nSimulando dia a dia (transacciones + pagos de cuota + cierre_diario)...")
    for offset in range(offset_inicial, dias_totales):
        fecha_simulada = inicio + timedelta(days=offset)
        _con_reintentos(lambda: _dia_completo(clientes, clientes_por_id, pagos_programados, fecha_simulada))
        if offset % 10 == 0:
            print(f"  dia {offset + 1}/{dias_totales} ({fecha_simulada}) listo")

    print(f"\nListo. Password de todos los clientes de prueba: {PASSWORD}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dias", type=int, default=75)
    parser.add_argument("--continuar", action="store_true",
                         help="reanuda una corrida cortada por un fallo de red, sin recrear clientes")
    args = parser.parse_args()
    simular(args.dias, continuar=args.continuar)
