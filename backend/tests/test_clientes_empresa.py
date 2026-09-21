RUC_VALIDO = "20100070970"
RUC_VALIDO_2 = "20131312955"


def _payload(**overrides):
    base = {
        "ruc": RUC_VALIDO, "razon_social": "Empresa de Prueba SAC",
        "representante_nombres": "Ana", "representante_apellidos": "Torres",
        "email": "representante@correo.pe", "telefono": None, "region": "Lima",
    }
    return {**base, **overrides}


def test_alta_empresarial_exitosa(cliente, token_admin, db):
    r = cliente.post("/backoffice/clientes-empresa", headers=token_admin, json=_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ruc"] == RUC_VALIDO
    assert len(body["numero_cuenta"]) == 14 and len(body["cci"]) == 20
    assert len(body["password_temporal"]) >= 12
    assert body["tarjeta"]["estado"] == "activa"

    from app.models import Cliente, Cuenta, AuditLog
    c = db.get(Cliente, body["cliente_id"])
    assert c.tipo_documento == "RUC" and c.segmento == "empresa" and c.razon_social == "Empresa de Prueba SAC"
    cuenta = db.get(Cuenta, body["cuenta_id"])
    assert cuenta.tipo_cuenta == "corriente"
    assert db.query(AuditLog).filter_by(accion="crear_cliente_empresa", entidad_id=str(c.cliente_id)).count() == 1


def test_ruc_invalido_da_422(cliente, token_admin):
    invalido = RUC_VALIDO[:-1] + str((int(RUC_VALIDO[-1]) + 1) % 10)
    r = cliente.post("/backoffice/clientes-empresa", headers=token_admin, json=_payload(ruc=invalido))
    assert r.status_code == 422


def test_ruc_que_no_es_persona_juridica_da_422(cliente, token_admin):
    r = cliente.post("/backoffice/clientes-empresa", headers=token_admin, json=_payload(ruc="10131312955"))
    assert r.status_code == 422


def test_ruc_duplicado_da_409(cliente, token_admin):
    cliente.post("/backoffice/clientes-empresa", headers=token_admin, json=_payload())
    r = cliente.post("/backoffice/clientes-empresa", headers=token_admin,
                      json=_payload(email="otro.representante@correo.pe"))
    assert r.status_code == 409


def test_analista_no_puede_crear_empresas(cliente, token_analista):
    r = cliente.post("/backoffice/clientes-empresa", headers=token_analista, json=_payload())
    assert r.status_code == 403


def test_autoservicio_nunca_crea_una_empresa(cliente):
    from conftest import MARIA
    r = cliente.post("/auth/registro", json={**MARIA, "tipo_documento": "RUC", "numero_documento": RUC_VALIDO})
    assert r.status_code == 422


def test_primer_acceso_de_la_empresa_exige_cambiar_password(cliente, token_admin):
    alta = cliente.post("/backoffice/clientes-empresa", headers=token_admin, json=_payload())
    email = _payload()["email"]
    password_temporal = alta.json()["password_temporal"]

    login = cliente.post("/auth/login", json={"email": email, "password": password_temporal})
    assert login.status_code == 200
    assert login.json()["debe_cambiar_password"] is True


def test_listado_de_empresas_muestra_ruc_completo(cliente, token_admin, db):
    cliente.post("/backoffice/clientes-empresa", headers=token_admin, json=_payload())

    r = cliente.get("/backoffice/clientes-empresa", headers=token_admin)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["ruc"] == RUC_VALIDO  # V13: el RUC no se enmascara

    from app.models import AuditLog
    assert db.query(AuditLog).filter_by(accion="consultar", entidad="clientes_empresa").count() == 1


def test_analista_no_puede_listar_empresas(cliente, token_analista):
    r = cliente.get("/backoffice/clientes-empresa", headers=token_analista)
    assert r.status_code == 403
