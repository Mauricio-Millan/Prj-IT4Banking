import re

from app.core.numeracion import digito_verificador
from app.models import Tarjeta

PASSWORD = "ClaveSegura1"  # ver MARIA en conftest.py


def _tarjeta_id(cliente, headers) -> int:
    return cliente.get("/tarjetas", headers=headers).json()[0]["tarjeta_id"]


def test_emision_genera_pan_valido_con_bin_y_ultimos4_consistentes(cliente, registrado, db):
    _, _, cuenta_id = registrado()
    tarjeta = db.query(Tarjeta).filter_by(cuenta_id=cuenta_id).one()
    assert tarjeta.pan_cifrado != b"" and tarjeta.pan_hmac != b""


def test_revelado_exitoso(cliente, registrado, db):
    headers, _, _ = registrado()
    tarjeta_id = _tarjeta_id(cliente, headers)

    r = cliente.post(f"/tarjetas/{tarjeta_id}/revelar", headers=headers, json={"password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"

    body = r.json()
    assert len(body["pan"]) == 16 and body["pan"].isdigit()
    assert digito_verificador(body["pan"][:-1]) == body["pan"][-1]
    assert re.fullmatch(r"\d{2}/\d{2}", body["vencimiento"])
    assert re.fullmatch(r"\d{3}", body["cvv"])
    assert body["titular"]

    from app.models import AuditLog
    assert db.query(AuditLog).filter_by(accion="revelar_tarjeta", entidad_id=str(tarjeta_id)).count() == 1


def test_revelado_dos_veces_da_cvv_con_formato_valido_ambas_veces(cliente, registrado):
    headers, _, _ = registrado()
    tarjeta_id = _tarjeta_id(cliente, headers)

    for _ in range(2):
        r = cliente.post(f"/tarjetas/{tarjeta_id}/revelar", headers=headers, json={"password": PASSWORD})
        assert re.fullmatch(r"\d{3}", r.json()["cvv"])


def test_password_incorrecta_da_401_y_no_expone_datos_de_tarjeta(cliente, registrado, db):
    headers, _, _ = registrado()
    tarjeta_id = _tarjeta_id(cliente, headers)

    r = cliente.post(f"/tarjetas/{tarjeta_id}/revelar", headers=headers, json={"password": "incorrecta"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Credenciales inválidas"}

    from app.models import AuditLog
    assert db.query(AuditLog).filter_by(accion="revelar_tarjeta_fallido", entidad_id=str(tarjeta_id)).count() == 1


def test_sexto_intento_en_15_minutos_da_429_incluso_con_password_correcta(cliente, registrado):
    headers, _, _ = registrado()
    tarjeta_id = _tarjeta_id(cliente, headers)

    for _ in range(5):
        r = cliente.post(f"/tarjetas/{tarjeta_id}/revelar", headers=headers, json={"password": "incorrecta"})
        assert r.status_code == 401

    r = cliente.post(f"/tarjetas/{tarjeta_id}/revelar", headers=headers, json={"password": PASSWORD})
    assert r.status_code == 429


def test_no_puede_revelar_tarjeta_ajena(cliente, registrado):
    headers_a, _, _ = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    tarjeta_b = _tarjeta_id(cliente, headers_b)

    r = cliente.post(f"/tarjetas/{tarjeta_b}/revelar", headers=headers_a, json={"password": PASSWORD})
    assert r.status_code == 404


def test_tarjeta_no_activa_da_409(cliente, registrado, db):
    headers, _, _ = registrado()
    tarjeta_id = _tarjeta_id(cliente, headers)
    db.query(Tarjeta).filter_by(tarjeta_id=tarjeta_id).update({"estado": "bloqueada"})
    db.commit()

    r = cliente.post(f"/tarjetas/{tarjeta_id}/revelar", headers=headers, json={"password": PASSWORD})
    assert r.status_code == 409


def test_listado_de_tarjetas_no_expone_pan_ni_cvv(cliente, registrado):
    headers, _, _ = registrado()
    r = cliente.get("/tarjetas", headers=headers)
    for tarjeta in r.json():
        assert "pan" not in tarjeta and "cvv" not in tarjeta and "pan_cifrado" not in tarjeta
