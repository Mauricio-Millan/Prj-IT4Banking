from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.jobs.cierre_diario import ejecutar
from app.models import AuditLog, Cliente, Cuenta, Cuota, Prestamo


def test_cierre_diario_marca_vencidas_y_calcula_mora(cliente, registrado, db, monkeypatch):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]

    cuota1 = db.query(Cuota).filter_by(prestamo_id=prestamo_id, numero=1).one()
    hoy = cuota1.fecha_vencimiento + timedelta(days=12)
    monkeypatch.setattr("app.jobs.cierre_diario.SessionLocal", sessionmaker(bind=db.get_bind()))

    ejecutar(hoy)

    db.refresh(cuota1)
    prestamo = db.get(Prestamo, prestamo_id)
    assert cuota1.estado == "vencida"
    assert prestamo.dias_mora == 12
    assert prestamo.bucket_mora == "1-30"
    assert db.query(AuditLog).filter_by(accion="cierre_diario", entidad_id=hoy.isoformat()).count() == 1


def test_cierre_diario_es_idempotente(cliente, registrado, db, monkeypatch):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]
    cuota1 = db.query(Cuota).filter_by(prestamo_id=prestamo_id, numero=1).one()
    hoy = cuota1.fecha_vencimiento + timedelta(days=12)
    monkeypatch.setattr("app.jobs.cierre_diario.SessionLocal", sessionmaker(bind=db.get_bind()))

    ejecutar(hoy)
    db.refresh(cuota1)
    prestamo = db.get(Prestamo, prestamo_id)
    estado_1, mora_1, bucket_1 = cuota1.estado, prestamo.dias_mora, prestamo.bucket_mora

    ejecutar(hoy)
    db.refresh(cuota1)
    db.refresh(prestamo)
    assert (cuota1.estado, prestamo.dias_mora, prestamo.bucket_mora) == (estado_1, mora_1, bucket_1)


def test_pago_regulariza_la_mora(cliente, registrado, db, monkeypatch):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]
    cuota1 = db.query(Cuota).filter_by(prestamo_id=prestamo_id, numero=1).one()
    hoy = cuota1.fecha_vencimiento + timedelta(days=12)
    monkeypatch.setattr("app.jobs.cierre_diario.SessionLocal", sessionmaker(bind=db.get_bind()))
    ejecutar(hoy)

    prestamo = db.get(Prestamo, prestamo_id)
    assert prestamo.dias_mora == 12

    pago = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert pago.status_code == 201, pago.text

    db.refresh(prestamo)
    assert prestamo.dias_mora == 0
    assert prestamo.bucket_mora == "0"


def test_cierre_diario_reevalua_segmento_de_los_clientes(cliente, registrado, db, monkeypatch):
    _, cliente_id, cuenta_id = registrado()
    db.query(Cuenta).filter_by(cuenta_id=cuenta_id).update({"saldo": Decimal("25000.00")})
    db.commit()
    monkeypatch.setattr("app.jobs.cierre_diario.SessionLocal", sessionmaker(bind=db.get_bind()))

    ejecutar(date.today())

    c = db.get(Cliente, cliente_id)
    assert c.segmento == "premium"
    assert db.query(AuditLog).filter_by(accion="cambio_segmento", entidad_id=str(cliente_id)).count() == 1


def test_cierre_diario_no_reevalua_empresas(cliente, token_admin, db, monkeypatch):
    alta = cliente.post("/backoffice/clientes-empresa", headers=token_admin, json={
        "ruc": "20100070970", "razon_social": "Empresa SAC", "representante_nombres": "Ana",
        "representante_apellidos": "Torres", "email": "empresa.cierre@correo.pe", "telefono": None, "region": "Lima",
    })
    cliente_id = alta.json()["cliente_id"]
    monkeypatch.setattr("app.jobs.cierre_diario.SessionLocal", sessionmaker(bind=db.get_bind()))

    ejecutar(date.today())

    assert db.get(Cliente, cliente_id).segmento == "empresa"
