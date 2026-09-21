from sqlalchemy.exc import IntegrityError

from app.core.security import decodificar_token
from app.models import AuditLog, Usuario


def test_admin_crea_analista_con_correo_corporativo(cliente, token_admin, db):
    r = cliente.post("/backoffice/usuarios", headers=token_admin,
                      json={"email": "ana.perez@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["activo"] is True and body["debe_cambiar_password"] is True
    assert db.query(AuditLog).filter_by(accion="crear_usuario_interno").count() == 1


def test_correo_no_corporativo_es_rechazado(cliente, token_admin):
    r = cliente.post("/backoffice/usuarios", headers=token_admin,
                      json={"email": "ana@gmail.com", "rol": "analista", "password_temporal": "TemporalSegura1"})
    assert r.status_code == 422


def test_analista_no_puede_gestionar_usuarios(cliente, token_analista):
    r = cliente.post("/backoffice/usuarios", headers=token_analista,
                      json={"email": "otro@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})
    assert r.status_code == 403


def test_identidad_fusionada_rechazada_por_check_constraint(db):
    from app.models import Cliente
    from datetime import date

    c = Cliente(codigo_cliente="1234567895", tipo_documento="DNI", numero_documento="99999999",
                nombres="X", apellidos="Y", fecha_nacimiento=date(1990, 1, 1), email="x@correo.pe", region="Lima")
    db.add(c)
    db.flush()
    db.add(Usuario(cliente_id=c.cliente_id, email="raro@bancocloud.pe", password_hash="x", rol="analista"))
    try:
        db.commit()
        assert False, "debia rechazar: analista con cliente_id no nulo"
    except IntegrityError:
        db.rollback()


def test_primer_acceso_obliga_a_cambiar_password(cliente, token_admin):
    cliente.post("/backoffice/usuarios", headers=token_admin,
                 json={"email": "nueva@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})

    r = cliente.post("/auth/login", json={"email": "nueva@bancocloud.pe", "password": "TemporalSegura1"})
    assert r.status_code == 200
    assert r.json()["debe_cambiar_password"] is True
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    bloqueado = cliente.get("/backoffice/prestamos", headers=headers)
    assert bloqueado.status_code == 403
    assert bloqueado.json()["detail"]["codigo"] == "CAMBIO_PASSWORD_REQUERIDO"

    cambio = cliente.post("/auth/cambiar-password", headers=headers,
                           json={"actual": "TemporalSegura1", "nueva": "NuevaClaveLarga1"})
    assert cambio.status_code == 204

    ya_puede = cliente.get("/backoffice/prestamos", headers=headers)
    assert ya_puede.status_code == 200


def test_cambiar_password_exige_12_caracteres_para_interno(cliente, token_admin):
    cliente.post("/backoffice/usuarios", headers=token_admin,
                 json={"email": "corta@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})
    r = cliente.post("/auth/login", json={"email": "corta@bancocloud.pe", "password": "TemporalSegura1"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r2 = cliente.post("/auth/cambiar-password", headers=headers, json={"actual": "TemporalSegura1", "nueva": "corta123"})
    assert r2.status_code == 422


def test_desactivar_revoca_acceso_en_la_siguiente_peticion(cliente, token_admin):
    r = cliente.post("/backoffice/usuarios", headers=token_admin,
                      json={"email": "temporal@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})
    usuario_id = r.json()["usuario_id"]
    login = cliente.post("/auth/login", json={"email": "temporal@bancocloud.pe", "password": "TemporalSegura1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    cliente.post("/auth/cambiar-password", headers=headers, json={"actual": "TemporalSegura1", "nueva": "NuevaClaveLarga1"})

    desactivar = cliente.patch(f"/backoffice/usuarios/{usuario_id}", headers=token_admin, json={"activo": False})
    assert desactivar.status_code == 200 and desactivar.json()["activo"] is False

    r3 = cliente.get("/backoffice/prestamos", headers=headers)
    assert r3.status_code == 401


def test_usuario_inactivo_no_inicia_sesion(cliente, token_admin):
    r = cliente.post("/backoffice/usuarios", headers=token_admin,
                      json={"email": "sedesactiva@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})
    usuario_id = r.json()["usuario_id"]
    cliente.patch(f"/backoffice/usuarios/{usuario_id}", headers=token_admin, json={"activo": False})

    login = cliente.post("/auth/login", json={"email": "sedesactiva@bancocloud.pe", "password": "TemporalSegura1"})
    assert login.status_code == 401
    assert login.json() == {"detail": "Credenciales inválidas"}


def test_admin_no_puede_desactivarse_ni_cambiar_su_propio_rol_si_es_el_unico(cliente, token_admin, admin):
    r1 = cliente.patch(f"/backoffice/usuarios/{admin.usuario_id}", headers=token_admin, json={"activo": False})
    assert r1.status_code == 409

    r2 = cliente.patch(f"/backoffice/usuarios/{admin.usuario_id}", headers=token_admin, json={"rol": "analista"})
    assert r2.status_code == 409


def test_bloqueo_por_intentos_fallidos_de_login(cliente, token_admin, db):
    cliente.post("/backoffice/usuarios", headers=token_admin,
                 json={"email": "bloqueado@bancocloud.pe", "rol": "analista", "password_temporal": "TemporalSegura1"})

    for _ in range(5):
        r = cliente.post("/auth/login", json={"email": "bloqueado@bancocloud.pe", "password": "mala"})
        assert r.status_code == 401

    r = cliente.post("/auth/login", json={"email": "bloqueado@bancocloud.pe", "password": "TemporalSegura1"})
    assert r.status_code == 401
    assert db.query(AuditLog).filter_by(accion="login_bloqueado").count() == 1


def test_sesion_backoffice_dura_15_minutos_cliente_30(cliente, token_admin, registrado):
    login_admin = cliente.post("/auth/login", json={"email": "admin@bancocloud.pe", "password": "Admin12345678"})
    claims_admin = decodificar_token(login_admin.json()["access_token"])
    assert abs((claims_admin["exp"] - claims_admin["iat"]) - 15 * 60) <= 2

    from conftest import MARIA
    registrado()
    login_cliente = cliente.post("/auth/login", json={"email": MARIA["email"], "password": MARIA["password"]})
    claims_cliente = decodificar_token(login_cliente.json()["access_token"])
    assert abs((claims_cliente["exp"] - claims_cliente["iat"]) - 30 * 60) <= 2
