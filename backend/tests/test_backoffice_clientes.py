def test_admin_ve_listado_de_clientes_con_sus_cuentas(cliente, registrado, token_admin, db):
    _, cliente_id, cuenta_id = registrado()

    r = cliente.get("/backoffice/clientes", headers=token_admin)
    assert r.status_code == 200, r.text
    body = r.json()
    fila = next(c for c in body["items"] if c["cliente_id"] == cliente_id)
    assert fila["codigo_cliente"] and fila["nombres"]
    assert any(c["cuenta_id"] == cuenta_id for c in fila["cuentas"])

    from app.models import AuditLog
    assert db.query(AuditLog).filter_by(accion="consultar", entidad="listado_clientes").count() == 1


def test_analista_no_puede_ver_listado_de_clientes(cliente, token_analista):
    r = cliente.get("/backoffice/clientes", headers=token_analista)
    assert r.status_code == 403


def test_listado_de_clientes_pagina(cliente, registrado, token_admin):
    for i in range(3):
        registrado(numero_documento=f"6000000{i}", email=f"pag{i}@correo.pe")

    r = cliente.get("/backoffice/clientes?pagina=1&tamano=2", headers=token_admin)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] >= 3
