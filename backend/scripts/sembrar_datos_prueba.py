"""Genera ~2 meses de actividad de prueba para probar la app con datos realistas:
- 20 clientes (cliente + usuario + cuenta + tarjeta, via el mismo onboarding.registrar()
  que usa la API real: numero_cuenta/cci/PAN cifrado quedan correctos).
- 10 a 20 transacciones por cliente (deposito/retiro/transferencia), con fecha_hora repartida
  en los ultimos 60 dias (se ejecutan "hoy" para que el saldo se calcule bien y luego se
  reetiqueta la fecha del registro ya creado).
- 8 clientes con una solicitud de prestamo, variando el segmento (joven/clasico = "basico",
  premium) y el monto (algunos dentro del limite -> vigente automatico, otros por encima ->
  solicitado, para tener cola de backoffice que revisar).

No es idempotente: usa DNIs y correos fijos, un segundo run choca con los UNIQUE existentes.
No es parte del reset de HU-Numeracion-Bancaria; es puramente para tener datos con los que
probar la app manualmente (pantallas de movimientos, backoffice de prestamos, etc.).
"""
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.models import AsientoContable, Cliente, Cuenta, Transaccion
from app.schemas.auth import RegistroIn
from app.schemas.prestamos import SolicitudPrestamoIn
from app.schemas.transacciones import TransaccionIn
from app.services import onboarding
from app.services import prestamos as prestamos_service
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
# 8 clientes que recibiran una solicitud de prestamo: (indice, monto, plazo)
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


def _backdatar_transaccion(db, transaccion: Transaccion, cuando: datetime) -> None:
    db.execute(update(Transaccion).where(Transaccion.transaccion_id == transaccion.transaccion_id).values(fecha_hora=cuando))
    db.execute(update(AsientoContable).where(AsientoContable.transaccion_id == transaccion.transaccion_id)
               .values(fecha_contable=cuando.date(), creado_en=cuando))
    db.commit()


def _saldo_actual(db, cuenta_id: int) -> Decimal:
    # select de la columna sola (no de la entidad Cuenta): evita leer un valor cacheado del
    # identity map, ya que SessionLocal usa expire_on_commit=False.
    return db.execute(select(Cuenta.saldo).where(Cuenta.cuenta_id == cuenta_id)).scalar()


def main() -> None:
    db = SessionLocal()
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
    print(f"\n{len(PREMIUM)} clientes promovidos a segmento premium: {sorted(PREMIUM)}")

    print("\nGenerando transacciones (60 dias hacia atras)...")
    for c in clientes:
        n_tx = random.randint(10, 20)
        # etiquetas de "hace N dias" en orden descendente: la primera transaccion (deposito
        # inicial) queda como la mas antigua, el resto se reparte hasta hoy.
        dias_atras = sorted(random.sample(range(1, 60), n_tx - 1), reverse=True) + [0]

        # deposito inicial para tener con que operar
        monto_inicial = Decimal(random.randint(800, 4000))
        tx = transacciones_service.crear(
            db, c["cliente_id"], c["usuario_id"],
            TransaccionIn(tipo="deposito", monto=monto_inicial, cuenta_destino=c["numero_cuenta"]),
        )
        cuando = datetime.now(timezone.utc) - timedelta(days=dias_atras[0], hours=random.randint(0, 23))
        _backdatar_transaccion(db, tx, cuando)

        for dias in dias_atras[1:]:
            saldo = _saldo_actual(db, c["cuenta_id"])
            tipo = random.choices(["deposito", "retiro", "transferencia"], weights=[0.4, 0.3, 0.3])[0]
            if saldo < Decimal("20.00"):
                tipo = "deposito"  # sin saldo para retirar/transferir

            try:
                if tipo == "deposito":
                    monto = Decimal(random.randint(50, 1500))
                    datos_tx = TransaccionIn(tipo="deposito", monto=monto, cuenta_destino=c["numero_cuenta"])
                elif tipo == "retiro":
                    monto = (saldo * Decimal(random.randint(5, 35)) / 100).quantize(Decimal("0.01"))
                    datos_tx = TransaccionIn(tipo="retiro", monto=max(monto, Decimal("10.00")), cuenta_origen_id=c["cuenta_id"])
                else:
                    destino = random.choice([o for o in clientes if o is not c])
                    monto = (saldo * Decimal(random.randint(5, 35)) / 100).quantize(Decimal("0.01"))
                    datos_tx = TransaccionIn(tipo="transferencia", monto=max(monto, Decimal("10.00")),
                                              cuenta_origen_id=c["cuenta_id"], cuenta_destino=destino["numero_cuenta"])
                tx = transacciones_service.crear(db, c["cliente_id"], c["usuario_id"], datos_tx)
            except Exception:
                db.rollback()
                continue

            cuando = datetime.now(timezone.utc) - timedelta(days=dias, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            _backdatar_transaccion(db, tx, cuando)
        print(f"  {n_tx} transacciones para cuenta {c['numero_cuenta']}")

    print("\nGenerando solicitudes de prestamo...")
    for idx, monto, plazo in SOLICITUDES_PRESTAMO:
        c = clientes[idx]
        p = prestamos_service.solicitar(db, c["cliente_id"], c["usuario_id"], SolicitudPrestamoIn(monto_original=monto, plazo=plazo))
        print(f"  cliente {idx + 1} ({c['numero_cuenta']}): monto {monto} -> estado {p.estado}")

    print("\nListo. Password de todos los clientes de prueba:", PASSWORD)


if __name__ == "__main__":
    main()
