import re


def _solicitar_grande(cliente, headers):
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "20000.00", "plazo": 24})
    assert r.json()["estado"] == "solicitado"
    return r


def test_analista_ve_cola_con_documento_enmascarado_y_nombre_completo(cliente, registrado, token_analista):
    headers, _, _ = registrado()
    _solicitar_grande(cliente, headers)

    r = cliente.get("/backoffice/prestamos", headers=token_analista)
    assert r.status_code == 200
    pendiente = r.json()[0]
    # HU-Enmascaramiento-PII-Backoffice: el DNI completo (MARIA = "45872103") nunca llega al analista.
    assert pendiente["cliente_documento"] == "****2103"
    assert re.fullmatch(r"\*+\d{4}", pendiente["cliente_documento"])
    assert "Fernanda" in pendiente["cliente_nombre"] or "fernanda" in pendiente["cliente_nombre"].lower()


def test_aprobar_deja_vigente_con_desembolso(cliente, registrado, token_analista):
    headers, _, _ = registrado()
    prestamo_id = _solicitar_grande(cliente, headers).json()["prestamo_id"]

    r = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "vigente"
    assert r.json()["fecha_desembolso"] is not None


def test_rechazar_deja_rechazado(cliente, registrado, token_analista):
    headers, _, _ = registrado()
    prestamo_id = _solicitar_grande(cliente, headers).json()["prestamo_id"]

    r = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "rechazar"})
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazado"


def test_rol_cliente_no_accede_a_backoffice(cliente, registrado):
    headers, _, _ = registrado()
    assert cliente.get("/backoffice/prestamos", headers=headers).status_code == 403
    assert cliente.patch("/backoffice/prestamos/1", headers=headers, json={"decision": "aprobar"}).status_code == 403


def test_resolver_dos_veces_da_409(cliente, registrado, token_analista):
    headers, _, _ = registrado()
    prestamo_id = _solicitar_grande(cliente, headers).json()["prestamo_id"]
    cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})

    r = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})
    assert r.status_code == 409


def test_solicitud_autodecidida_no_aparece_en_cola(cliente, registrado, token_analista):
    headers, _, _ = registrado()
    cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "1000.00", "plazo": 6})

    r = cliente.get("/backoffice/prestamos", headers=token_analista)
    assert r.json() == []


def test_conflicto_de_interes_solo_lo_resuelve_un_admin(cliente, registrado, token_analista, token_admin, db):
    headers, cliente_id, _ = registrado()
    prestamo_id = _solicitar_grande(cliente, headers).json()["prestamo_id"]

    r = cliente.patch(f"/backoffice/clientes/{cliente_id}/es-empleado", headers=token_admin, json={"es_empleado": True})
    assert r.status_code == 204

    r_analista = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_analista, json={"decision": "aprobar"})
    assert r_analista.status_code == 403

    r_admin = cliente.patch(f"/backoffice/prestamos/{prestamo_id}", headers=token_admin, json={"decision": "aprobar"})
    assert r_admin.status_code == 200


def test_consultar_cola_de_prestamos_deja_rastro_en_audit_log(cliente, registrado, token_analista, db):
    headers, _, _ = registrado()
    _solicitar_grande(cliente, headers)

    from app.models import AuditLog

    cliente.get("/backoffice/prestamos", headers=token_analista)
    assert db.query(AuditLog).filter_by(accion="consultar", entidad="cola_prestamos").count() == 1
