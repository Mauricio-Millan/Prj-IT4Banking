from datetime import date

from app.core.security import decodificar_token
from app.models import AuditLog, Cuenta, Tarjeta
from app.models.cuenta import fecha_vencimiento_tarjeta
from conftest import MARIA


def test_registro_crea_cliente_usuario_cuenta_y_token(cliente, db):
    r = cliente.post("/auth/registro", json=MARIA)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["segmento"] == "clasico"
    claims = decodificar_token(body["access_token"])
    assert claims["rol"] == "cliente" and claims["cliente_id"] == body["cliente_id"]
    cuenta = db.get(Cuenta, body["cuenta_id"])
    assert cuenta.tipo_cuenta == "ahorro" and float(cuenta.saldo) == 0
    assert db.query(AuditLog).filter_by(entidad="cliente", accion="crear").count() == 1


def test_registro_emite_tarjeta_debito_activa_sin_datos_sensibles(cliente, db):
    r = cliente.post("/auth/registro", json=MARIA)
    assert r.status_code == 201, r.text
    body = r.json()
    tarjeta = body["tarjeta"]

    # exactamente una tarjeta, asociada a la cuenta creada en el mismo registro
    assert db.query(Tarjeta).filter_by(cuenta_id=body["cuenta_id"]).count() == 1
    assert tarjeta["tipo_tarjeta"] == "debito" and tarjeta["estado"] == "activa"
    assert len(tarjeta["ultimos_4"]) == 4 and tarjeta["ultimos_4"].isdigit()

    # nunca un PAN completo ni CVV en la respuesta
    assert "pan" not in tarjeta and "numero" not in tarjeta and "cvv" not in tarjeta

    hoy = date.today()
    assert tarjeta["fecha_emision"] == hoy.isoformat()
    assert tarjeta["fecha_vencimiento"] == fecha_vencimiento_tarjeta(hoy).isoformat()


def test_registro_duplicado_no_emite_tarjeta(cliente, db):
    cliente.post("/auth/registro", json=MARIA)
    r = cliente.post("/auth/registro", json={**MARIA, "email": "otra@correo.pe"})
    assert r.status_code == 409
    assert db.query(Tarjeta).count() == 1  # la del primer registro, nada mas


def test_tarjeta_emitida_visible_de_inmediato_en_get_tarjetas(cliente):
    r = cliente.post("/auth/registro", json=MARIA)
    body = r.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    r2 = cliente.get("/tarjetas", headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["ultimos_4"] == body["tarjeta"]["ultimos_4"]


def test_fecha_vencimiento_tarjeta_fin_de_mes_evita_29_febrero():
    assert fecha_vencimiento_tarjeta(date(2026, 9, 20)) == date(2030, 9, 30)
    assert fecha_vencimiento_tarjeta(date(2024, 2, 29)) == date(2028, 2, 29)  # 2028 es bisiesto
    assert fecha_vencimiento_tarjeta(date(2023, 2, 28)) == date(2027, 2, 28)  # 2027 no es bisiesto


def test_registro_normaliza_y_rechaza_duplicados(cliente):
    assert cliente.post("/auth/registro", json=MARIA).status_code == 201
    r = cliente.post("/auth/registro", json={**MARIA, "email": "otra@correo.pe"})
    assert r.status_code == 409 and r.json()["detail"]["campo"] == "numero_documento"
    r = cliente.post("/auth/registro", json={**MARIA, "numero_documento": "11111111"})
    assert r.status_code == 409 and r.json()["detail"]["campo"] == "email"


def test_registro_rechaza_correo_corporativo(cliente):
    # V3: un cliente no puede aparentar ser personal del banco.
    r = cliente.post("/auth/registro", json={**MARIA, "email": "impostor@bancocloud.pe"})
    assert r.status_code == 422


def test_registro_valida_dni_y_edad(cliente):
    assert cliente.post("/auth/registro", json={**MARIA, "numero_documento": "123"}).status_code == 422
    assert cliente.post("/auth/registro", json={**MARIA, "fecha_nacimiento": "2015-01-01"}).status_code == 422
    assert cliente.post("/auth/registro", json={**MARIA, "password": "corta"}).status_code == 422


def test_login_devuelve_token_y_registra_auditoria(cliente, db):
    cliente.post("/auth/registro", json=MARIA)
    r = cliente.post("/auth/login", json={"email": MARIA["email"], "password": MARIA["password"]})
    assert r.status_code == 200, r.text
    claims = decodificar_token(r.json()["access_token"])
    assert claims["rol"] == "cliente" and claims["cliente_id"] is not None
    assert db.query(AuditLog).filter_by(entidad="usuario", accion="login").count() == 1


def test_login_password_incorrecta_401(cliente):
    cliente.post("/auth/registro", json=MARIA)
    r = cliente.post("/auth/login", json={"email": MARIA["email"], "password": "otra-clave"})
    assert r.status_code == 401


def test_login_email_inexistente_mismo_mensaje(cliente):
    cliente.post("/auth/registro", json=MARIA)
    r_malo = cliente.post("/auth/login", json={"email": MARIA["email"], "password": "otra-clave"})
    r_inexistente = cliente.post("/auth/login", json={"email": "no-existe@correo.pe", "password": "cualquiera"})
    assert r_malo.status_code == r_inexistente.status_code == 401
    assert r_malo.json() == r_inexistente.json()
