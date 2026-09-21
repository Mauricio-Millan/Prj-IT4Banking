"""HU-Libro-Mayor-Partida-Doble: cada deposito/retiro/transferencia genera un asiento
contable balanceado ademas de actualizar cuenta.saldo. Ver Docs/Proyecto/
Arquitectura-Core-Banking-Tecnica.md §2.1 y HU-Libro-Mayor-Partida-Doble.md."""
import os
import tempfile
import threading
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import AsientoDesbalanceado, SaldoInsuficiente
from app.core.numeracion import cci_de, generar_numero_cuenta
from app.models import AsientoContable, Cliente, Cuenta, CuentaContable, MovimientoContable
from app.models.contabilidad import filas_seed_plan_de_cuentas
from app.services import transacciones as svc
from app.schemas.transacciones import TransaccionIn


def _asiento_de(db, transaccion_id):
    return db.scalar(select(AsientoContable).where(AsientoContable.transaccion_id == transaccion_id))


def _numero(db, cuenta_id):
    return db.get(Cuenta, cuenta_id).numero_cuenta


def _saldo_reconciliado(db, cuenta_id) -> Decimal:
    """SUM(HABER) - SUM(DEBE) de movimiento_contable para una cuenta_cliente_id."""
    haber = db.scalar(
        select(func.coalesce(func.sum(MovimientoContable.importe), 0)).where(
            MovimientoContable.cuenta_cliente_id == cuenta_id, MovimientoContable.tipo_movimiento == "H"
        )
    )
    debe = db.scalar(
        select(func.coalesce(func.sum(MovimientoContable.importe), 0)).where(
            MovimientoContable.cuenta_cliente_id == cuenta_id, MovimientoContable.tipo_movimiento == "D"
        )
    )
    return Decimal(haber) - Decimal(debe)


def test_deposito_genera_asiento_balanceado(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "deposito", "monto": "300.00", "cuenta_destino": _numero(db, cuenta_id)})
    assert r.status_code == 201, r.text

    asiento = _asiento_de(db, r.json()["transaccion_id"])
    assert asiento is not None and asiento.tipo_operacion == "deposito" and asiento.estado == "contabilizado"
    assert len(asiento.movimientos) == 2
    suma_d = sum(m.importe for m in asiento.movimientos if m.tipo_movimiento == "D")
    suma_h = sum(m.importe for m in asiento.movimientos if m.tipo_movimiento == "H")
    assert suma_d == suma_h == Decimal("300.00")
    assert any(m.cuenta_cliente_id == cuenta_id and m.tipo_movimiento == "H" for m in asiento.movimientos)


def test_retiro_con_saldo_suficiente_genera_asiento_balanceado(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    cliente.post("/transacciones", headers=headers,
                 json={"tipo": "deposito", "monto": "1300.00", "cuenta_destino": _numero(db, cuenta_id)})
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "retiro", "monto": "200.00", "cuenta_origen_id": cuenta_id})
    assert r.status_code == 201, r.text

    asiento = _asiento_de(db, r.json()["transaccion_id"])
    assert len(asiento.movimientos) == 2
    assert {m.tipo_movimiento for m in asiento.movimientos} == {"D", "H"}
    assert db.get(Cuenta, cuenta_id).saldo == Decimal("1100.00")


def test_retiro_con_saldo_insuficiente_no_deja_rastro_contable(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    total_antes = db.scalar(select(func.count()).select_from(AsientoContable))

    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "retiro", "monto": "500.00", "cuenta_origen_id": cuenta_id})
    assert r.status_code == 422

    assert db.get(Cuenta, cuenta_id).saldo == Decimal("0.00")
    assert db.scalar(select(func.count()).select_from(AsientoContable)) == total_antes
    assert db.scalar(select(func.count()).select_from(MovimientoContable)) == 0


def test_transferencia_intrabancaria_un_asiento_balanceado_con_ambas_cuentas(cliente, registrado, db):
    headers_a, _, cuenta_a = registrado()
    _, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "deposito", "monto": "1000.00", "cuenta_destino": _numero(db, cuenta_a)})

    r = cliente.post("/transacciones", headers=headers_a,
                      json={"tipo": "transferencia", "monto": "300.00",
                            "cuenta_origen_id": cuenta_a, "cuenta_destino": _numero(db, cuenta_b)})
    assert r.status_code == 201, r.text

    asiento = _asiento_de(db, r.json()["transaccion_id"])
    assert len(asiento.movimientos) == 2
    cuentas_referenciadas = {m.cuenta_cliente_id for m in asiento.movimientos}
    assert cuentas_referenciadas == {cuenta_a, cuenta_b}
    suma_d = sum(m.importe for m in asiento.movimientos if m.tipo_movimiento == "D")
    suma_h = sum(m.importe for m in asiento.movimientos if m.tipo_movimiento == "H")
    assert suma_d == suma_h
    assert db.get(Cuenta, cuenta_a).saldo == Decimal("700.00")
    assert db.get(Cuenta, cuenta_b).saldo == Decimal("300.00")


def test_transferencia_entre_monedas_distintas_no_toca_el_ledger(cliente, registrado, db):
    headers_a, cliente_a, cuenta_a = registrado()
    _, cliente_b, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    numero_usd = generar_numero_cuenta("USD")
    cuenta_usd = Cuenta(cliente_id=cliente_b, tipo_cuenta="ahorro", moneda="USD", saldo=0,
                         numero_cuenta=numero_usd, cci=cci_de(numero_usd))
    db.add(cuenta_usd)
    db.commit()
    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "deposito", "monto": "500.00", "cuenta_destino": _numero(db, cuenta_a)})
    total_antes = db.scalar(select(func.count()).select_from(AsientoContable))

    r = cliente.post("/transacciones", headers=headers_a,
                      json={"tipo": "transferencia", "monto": "50.00",
                            "cuenta_origen_id": cuenta_a, "cuenta_destino": numero_usd})
    assert r.status_code == 422
    assert db.scalar(select(func.count()).select_from(AsientoContable)) == total_antes


def test_reconciliacion_saldo_materializado_igual_a_suma_del_libro_mayor(cliente, registrado, db):
    headers_a, _, cuenta_a = registrado()
    headers_b, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "deposito", "monto": "1000.00", "cuenta_destino": _numero(db, cuenta_a)})
    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "retiro", "monto": "150.00", "cuenta_origen_id": cuenta_a})
    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "transferencia", "monto": "200.00",
                       "cuenta_origen_id": cuenta_a, "cuenta_destino": _numero(db, cuenta_b)})

    for cuenta_id in (cuenta_a, cuenta_b):
        assert _saldo_reconciliado(db, cuenta_id) == db.get(Cuenta, cuenta_id).saldo


def test_asiento_desbalanceado_por_bug_de_codigo_es_rechazado_en_codigo():
    """Defensa en profundidad, mitad testeable en SQLite: el trigger SQL vive en la migracion
    (T-SQL, solo corre en Azure SQL/SQL Server) pero el guard de codigo es el mismo para
    cualquier motor y es lo que realmente evita persistir un asiento roto."""
    movimientos_rotos = [
        MovimientoContable(cuenta_contable_id=1, tipo_movimiento="D", importe=Decimal("100.00"), moneda="PEN"),
        MovimientoContable(cuenta_contable_id=2, tipo_movimiento="H", importe=Decimal("99.00"), moneda="PEN"),
    ]
    try:
        svc.verificar_balance(movimientos_rotos)
        assert False, "debia lanzar AsientoDesbalanceado"
    except AsientoDesbalanceado:
        pass


def test_dos_retiros_concurrentes_no_producen_saldo_negativo():
    """Dos sesiones DB paralelas (threads) contra el mismo archivo SQLite: el UPDATE ... WHERE
    saldo >= monto serializa las escrituras a nivel de motor; exactamente uno de los dos retiros
    debe aplicarse."""
    fd, ruta = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # timeout alto: sin el, un segundo escritor concurrente puede chocar con "database is
        # locked" (excepcion distinta a SaldoInsuficiente) en vez de esperar su turno y ver el
        # estado ya actualizado — SQLite serializa escritores a nivel de archivo, no de fila.
        engine = create_engine(f"sqlite:///{ruta}", connect_args={"timeout": 30})
        Sesion = sessionmaker(bind=engine)
        from app.models import Base
        Base.metadata.create_all(engine)

        with Sesion() as s:
            s.add_all(CuentaContable(**f) for f in filas_seed_plan_de_cuentas())
            cliente_ = Cliente(codigo_cliente="9999999997", tipo_documento="DNI", numero_documento="99999999",
                                nombres="Test", apellidos="Concurrencia", fecha_nacimiento=date(1990, 1, 1),
                                email="conc@correo.pe", region="Lima", segmento="clasico")
            numero = generar_numero_cuenta("PEN")
            cuenta = Cuenta(cliente=cliente_, tipo_cuenta="ahorro", moneda="PEN", saldo=Decimal("500.00"),
                             numero_cuenta=numero, cci=cci_de(numero))
            s.add_all([cliente_, cuenta])
            s.commit()
            cliente_id, cuenta_id = cliente_.cliente_id, cuenta.cuenta_id

        resultados = []

        def intentar_retiro():
            with Sesion() as s:
                try:
                    datos = TransaccionIn(tipo="retiro", monto=Decimal("400.00"), cuenta_origen_id=cuenta_id)
                    svc.crear(s, cliente_id, usuario_id=1, datos=datos)
                    resultados.append("ok")
                except SaldoInsuficiente:
                    resultados.append("rechazado")

        hilos = [threading.Thread(target=intentar_retiro) for _ in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert sorted(resultados) == ["ok", "rechazado"]
        with Sesion() as s:
            assert s.get(Cuenta, cuenta_id).saldo == Decimal("100.00")
    finally:
        engine.dispose()  # Windows no libera el archivo hasta cerrar todas las conexiones del pool
        os.remove(ruta)
