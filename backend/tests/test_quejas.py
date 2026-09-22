def test_registro_y_clasificacion_exitosa(cliente, registrado, db):
    headers, _, _ = registrado()
    r = cliente.post("/quejas", headers=headers,
                      json={"texto": "Me cobraron una comisión que no sabía que existía en mi cuenta de ahorros"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado_revision"] == "pendiente"
    assert body["categoria_sugerida"] == "producto"  # proveedor falso: "comision"/"cuenta" -> producto

    from app.models import GenaiLog
    assert db.query(GenaiLog).filter_by(caso_uso="clasificar_queja", entidad_id=body["queja_id"]).count() == 1


def test_queja_de_fraude_queda_en_prioridad_alta(cliente, registrado, db):
    from app.models import Queja

    headers, _, _ = registrado()
    r = cliente.post("/quejas", headers=headers, json={"texto": "Hay un retiro que yo no reconozco en mi cuenta"})
    assert r.status_code == 201, r.text
    assert r.json()["categoria_sugerida"] == "fraude"

    queja = db.get(Queja, r.json()["queja_id"])
    assert queja.prioridad == "alta"


def test_lista_solo_quejas_propias(cliente, registrado):
    headers_a, _, _ = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/quejas", headers=headers_a, json={"texto": "Queja de prueba con texto suficiente"})
    cliente.post("/quejas", headers=headers_b, json={"texto": "Otra queja de prueba con texto suficiente"})

    r = cliente.get("/quejas", headers=headers_a)
    assert r.status_code == 200 and len(r.json()) == 1


def test_cuota_diaria_de_quejas(cliente, registrado):
    headers, _, _ = registrado()
    for i in range(5):
        r = cliente.post("/quejas", headers=headers, json={"texto": f"Queja numero {i} con texto suficiente"})
        assert r.status_code == 201, r.text

    r6 = cliente.post("/quejas", headers=headers, json={"texto": "Sexta queja del dia con texto suficiente"})
    assert r6.status_code == 429
