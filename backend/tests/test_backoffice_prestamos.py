import re


def _solicitar_grande(cliente, headers, cuenta_id):
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "20000.00", "plazo": 24, "cuenta_id": cuenta_id})
    assert r.json()["estado"] == "solicitado"
    return r


def test_analista_ve_cola_con_documento_enmascarado_y_nombre_completo(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)

    r = cliente.get("/backoffice/prestamos", headers=token_analista)
    assert r.status_code == 200
    pendiente = r.json()[0]
    # HU-Enmascaramiento-PII-Backoffice: el DNI completo (MARIA = "45872103") nunca llega al analista.
    assert pendiente["cliente_documento"] == "****2103"
    assert re.fullmatch(r"\*+\d{4}", pendiente["cliente_documento"])
    assert "Fernanda" in pendiente["cliente_nombre"] or "fernanda" in pendiente["cliente_nombre"].lower()


def test_aprobar_deja_vigente_con_desembolso(cliente, registrado, token_analista, db):
    headers, _, cuenta_id = registrado()
    prestamo_id = _solicitar_grande(cliente, headers, cuenta_id).json()["prestamo_id"]

    r = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "vigente"
    assert r.json()["fecha_desembolso"] is not None
    assert r.json()["cuotas_total"] == 24

    from app.models import Cuenta
    assert db.get(Cuenta, cuenta_id).saldo == 20000


def test_rechazar_deja_rechazado(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    prestamo_id = _solicitar_grande(cliente, headers, cuenta_id).json()["prestamo_id"]

    r = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "rechazar"})
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazado"


def test_rol_cliente_no_accede_a_backoffice(cliente, registrado):
    headers, _, _ = registrado()
    assert cliente.get("/backoffice/prestamos", headers=headers).status_code == 403
    assert cliente.patch("/backoffice/prestamos/1", headers=headers, json={"decision": "aprobar"}).status_code == 403


def test_resolver_dos_veces_da_409(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    prestamo_id = _solicitar_grande(cliente, headers, cuenta_id).json()["prestamo_id"]
    cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})

    r = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})
    assert r.status_code == 409


def test_solicitud_autodecidida_no_aparece_en_cola(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "1000.00", "plazo": 6, "cuenta_id": cuenta_id})

    r = cliente.get("/backoffice/prestamos", headers=token_analista)
    assert r.json() == []


def test_conflicto_de_interes_solo_lo_resuelve_un_admin(cliente, registrado, token_analista, token_admin, db):
    headers, cliente_id, cuenta_id = registrado()
    prestamo_id = _solicitar_grande(cliente, headers, cuenta_id).json()["prestamo_id"]

    r = cliente.patch(f"/backoffice/clientes/{cliente_id}/es-empleado", headers=token_admin, json={"es_empleado": True})
    assert r.status_code == 204

    r_analista = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})
    assert r_analista.status_code == 403

    r_admin = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_admin, json={"decision": "aprobar"})
    assert r_admin.status_code == 200


def test_consultar_cola_de_prestamos_deja_rastro_en_audit_log(cliente, registrado, token_analista, db):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)

    from app.models import AuditLog

    cliente.get("/backoffice/prestamos", headers=token_analista)
    assert db.query(AuditLog).filter_by(accion="consultar", entidad="cola_prestamos").count() == 1


# --- HU-Backoffice-Cartera-Prestamos ---

def test_sin_parametros_se_comporta_igual_que_antes(cliente, registrado, token_analista, db):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)
    prestamo_id = cliente.get("/backoffice/prestamos", headers=token_analista).json()[0]["prestamo_id"]
    cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})

    r = cliente.get("/backoffice/prestamos", headers=token_analista)
    assert r.json() == []  # el ahora-vigente no aparece sin filtro (default sigue siendo "solicitado")


def test_filtrar_por_estado_vigente_incluye_mora(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "1000.00", "plazo": 6, "cuenta_id": cuenta_id})
    assert r.json()["estado"] == "vigente"

    r = cliente.get("/backoffice/prestamos?estado=vigente", headers=token_analista)
    assert r.status_code == 200
    fila = r.json()[0]
    assert fila["estado"] == "vigente"
    assert "saldo_capital" in fila and "dias_mora" in fila and "bucket_mora" in fila


def test_estado_todos_devuelve_todos_los_estados(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "1000.00", "plazo": 6, "cuenta_id": cuenta_id})
    _solicitar_grande(cliente, headers, cuenta_id)

    r = cliente.get("/backoffice/prestamos?estado=todos", headers=token_analista)
    estados = {p["estado"] for p in r.json()}
    assert estados == {"vigente", "solicitado"}


def test_estado_invalido_da_422(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)

    r = cliente.get("/backoffice/prestamos?estado=inventado", headers=token_analista)
    assert r.status_code == 422


def test_buscar_por_codigo_de_cliente_exacto(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)
    codigo = cliente.get("/backoffice/prestamos?estado=todos", headers=token_analista).json()[0]["codigo_cliente"]

    r = cliente.get(f"/backoffice/prestamos?estado=todos&codigo_cliente={codigo}", headers=token_analista)
    assert len(r.json()) == 1
    assert r.json()[0]["codigo_cliente"] == codigo


def test_codigo_cliente_inexistente_da_lista_vacia_no_error(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)

    r = cliente.get("/backoffice/prestamos?estado=todos&codigo_cliente=0000000000", headers=token_analista)
    assert r.status_code == 200
    assert r.json() == []


def test_codigo_cliente_visible_documento_enmascarado(cliente, registrado, token_analista):
    headers, _, cuenta_id = registrado()
    _solicitar_grande(cliente, headers, cuenta_id)

    fila = cliente.get("/backoffice/prestamos?estado=todos", headers=token_analista).json()[0]
    assert fila["codigo_cliente"] and re.fullmatch(r"\*+\d{4}", fila["cliente_documento"])
