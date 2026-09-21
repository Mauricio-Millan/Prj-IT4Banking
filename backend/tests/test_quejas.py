def test_crear_queja_queda_pendiente_sin_clasificar(cliente, registrado):
    headers, _, _ = registrado()
    r = cliente.post("/quejas", headers=headers, json={"texto": "El cajero de Av. Arequipa no me entregó el efectivo"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado_revision"] == "pendiente"
    assert body["categoria_sugerida"] is None


def test_lista_solo_quejas_propias(cliente, registrado):
    headers_a, _, _ = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/quejas", headers=headers_a, json={"texto": "Queja de prueba con texto suficiente"})
    cliente.post("/quejas", headers=headers_b, json={"texto": "Otra queja de prueba con texto suficiente"})

    r = cliente.get("/quejas", headers=headers_a)
    assert r.status_code == 200 and len(r.json()) == 1
