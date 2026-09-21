def test_lista_solo_cuentas_propias(cliente, registrado):
    headers_a, _, cuenta_a = registrado()
    headers_b, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")

    r = cliente.get("/cuentas", headers=headers_a)
    assert r.status_code == 200
    ids = [c["cuenta_id"] for c in r.json()]
    assert ids == [cuenta_a] and cuenta_b not in ids


def test_saldo_de_cuenta_ajena_da_404(cliente, registrado):
    _, _, cuenta_a = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")

    assert cliente.get(f"/cuentas/{cuenta_a}/saldo", headers=headers_b).status_code == 404
    assert cliente.get("/cuentas/9999/saldo", headers=headers_b).status_code == 404


def test_movimientos_de_cuenta_ajena_da_404(cliente, registrado):
    _, _, cuenta_a = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    assert cliente.get(f"/cuentas/{cuenta_a}/movimientos", headers=headers_b).status_code == 404


def test_sin_token_da_401(cliente):
    assert cliente.get("/cuentas").status_code == 401
