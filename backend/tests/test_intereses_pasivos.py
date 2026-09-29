from datetime import date
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.jobs.cierre_diario import ejecutar as cierre_diario
from app.models import AsientoContable, Cuenta, MovimientoContable
from app.services.intereses_pasivos import _tasa_diaria, devengar_interes_pasivo


def test_tasa_diaria_valores_fijos():
    tasa = _tasa_diaria(Decimal("2.50"))
    esperado = (1 + Decimal("2.50") / 100) ** (Decimal(1) / 360) - 1
    assert tasa == esperado
    assert Decimal("0.00006") < tasa < Decimal("0.00008")  # ~2.5%/360 en orden de magnitud


def _depositar(cliente, headers, numero_cuenta, monto):
    return cliente.post("/transacciones", headers=headers,
                         json={"tipo": "deposito", "monto": monto, "cuenta_destino": numero_cuenta, "canal": "agente"})


def test_devengo_en_cuenta_de_ahorro_acredita_y_deja_asiento(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "10000.00")

    cuenta = db.get(Cuenta, cuenta_id)
    saldo_antes = cuenta.saldo
    fecha = date(2026, 9, 20)
    devengar_interes_pasivo(db, cuenta, fecha)
    db.commit()
    db.refresh(cuenta)

    interes_esperado = (saldo_antes * _tasa_diaria(settings.tea_pasiva_ahorro)).quantize(Decimal("0.01"))
    assert cuenta.saldo == saldo_antes + interes_esperado

    asiento = db.query(AsientoContable).filter_by(tipo_operacion="interes_pasivo", fecha_contable=fecha).one()
    assert asiento.transaccion_id is None
    movs = db.query(MovimientoContable).filter_by(asiento_id=asiento.asiento_id).all()
    assert {m.tipo_movimiento for m in movs} == {"D", "H"}
    assert all(m.importe == interes_esperado for m in movs)
    haber = next(m for m in movs if m.tipo_movimiento == "H")
    assert haber.cuenta_cliente_id == cuenta_id


def test_sin_devengo_en_cuenta_corriente(cliente, token_admin, db):
    r = cliente.post("/backoffice/clientes-empresa", headers=token_admin, json={
        "ruc": "20100070970", "razon_social": "Empresa de Prueba SAC", "representante_nombres": "Ana",
        "representante_apellidos": "Torres", "email": "representante@correo.pe", "telefono": None, "region": "Lima",
    })
    assert r.status_code == 201, r.text
    cuenta = db.get(Cuenta, r.json()["cuenta_id"])
    assert cuenta.tipo_cuenta == "corriente"

    devengar_interes_pasivo(db, cuenta, date(2026, 9, 20))
    db.commit()

    assert db.query(AsientoContable).filter_by(tipo_operacion="interes_pasivo").count() == 0


def test_sin_devengo_si_el_interes_redondea_a_cero(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "0.05")

    cuenta = db.get(Cuenta, cuenta_id)
    devengar_interes_pasivo(db, cuenta, date(2026, 9, 20))
    db.commit()
    db.refresh(cuenta)

    assert cuenta.saldo == Decimal("0.05")
    assert db.query(AsientoContable).filter_by(tipo_operacion="interes_pasivo").count() == 0


def test_devengo_no_se_duplica_si_se_corre_dos_veces_el_mismo_dia(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "10000.00")

    fecha = date(2026, 9, 20)
    cuenta = db.get(Cuenta, cuenta_id)
    devengar_interes_pasivo(db, cuenta, fecha)
    db.commit()
    db.refresh(cuenta)
    saldo_tras_primer_devengo = cuenta.saldo

    devengar_interes_pasivo(db, cuenta, fecha)  # mismo dia otra vez
    db.commit()
    db.refresh(cuenta)

    assert cuenta.saldo == saldo_tras_primer_devengo
    assert db.query(AsientoContable).filter_by(tipo_operacion="interes_pasivo", fecha_contable=fecha).count() == 1


def test_cierre_diario_devenga_interes_de_todas_las_cuentas_de_ahorro(cliente, registrado, db, monkeypatch):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "10000.00")
    monkeypatch.setattr("app.jobs.cierre_diario.SessionLocal", sessionmaker(bind=db.get_bind()))

    saldo_antes = db.get(Cuenta, cuenta_id).saldo
    cierre_diario(date(2026, 9, 20))
    db.expire_all()

    assert db.get(Cuenta, cuenta_id).saldo > saldo_antes
    assert db.query(AsientoContable).filter_by(tipo_operacion="interes_pasivo").count() >= 1
