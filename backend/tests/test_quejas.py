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


# --- Extension 2026-10-02: formulario de queja completo ---

def test_registrar_con_tipo_legal_y_pedido_consumidor(cliente, registrado, token_analista):
    headers, _, _ = registrado()
    r = cliente.post("/quejas", headers=headers, json={
        "texto": "Me cobraron una comision que no sabia que existia en mi cuenta",
        "tipo_legal": "reclamo", "pedido_consumidor": "quiero que me devuelvan el cobro",
    })
    assert r.status_code == 201, r.text
    queja_id = r.json()["queja_id"]

    cola = cliente.get("/backoffice/quejas", headers=token_analista).json()
    fila = next(q for q in cola if q["queja_id"] == queja_id)
    assert fila["tipo_legal"] == "reclamo"
    assert fila["pedido_consumidor"] == "quiero que me devuelvan el cobro"


def test_mas_de_una_referencia_a_la_vez_se_rechaza(cliente, registrado):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/quejas", headers=headers, json={
        "texto": "Queja de prueba con texto suficiente", "cuenta_id": cuenta_id, "tarjeta_id": 1,
    })
    assert r.status_code == 422


def test_referenciar_tarjeta_ajena_da_404(cliente, registrado, db):
    from sqlalchemy import select

    from app.models import Tarjeta

    headers_b, _, _ = registrado(numero_documento="70099001", email="b@correo.pe")
    _, _, cuenta_c = registrado(numero_documento="70099002", email="c@correo.pe")
    tarjeta_c = db.scalar(select(Tarjeta).where(Tarjeta.cuenta_id == cuenta_c))

    r = cliente.post("/quejas", headers=headers_b, json={
        "texto": "Alguien uso mi tarjeta sin autorizacion", "tarjeta_id": tarjeta_c.tarjeta_id,
    })
    assert r.status_code == 404


def test_fecha_incidente_futura_se_rechaza(cliente, registrado):
    from datetime import date, timedelta

    headers, _, _ = registrado()
    manana = (date.today() + timedelta(days=1)).isoformat()
    r = cliente.post("/quejas", headers=headers, json={
        "texto": "Queja de prueba con texto suficiente", "fecha_incidente": manana,
    })
    assert r.status_code == 422


def test_referencia_propia_se_acepta_y_aparece_resuelta(cliente, registrado, token_analista, db):
    from sqlalchemy import select

    from app.models import Tarjeta

    headers, _, cuenta_id = registrado()
    tarjeta = db.scalar(select(Tarjeta).where(Tarjeta.cuenta_id == cuenta_id))
    r = cliente.post("/quejas", headers=headers, json={
        "texto": "Alguien uso mi tarjeta sin autorizacion", "tarjeta_id": tarjeta.tarjeta_id,
    })
    assert r.status_code == 201, r.text
    queja_id = r.json()["queja_id"]

    cola = cliente.get("/backoffice/quejas", headers=token_analista).json()
    fila = next(q for q in cola if q["queja_id"] == queja_id)
    assert fila["referencia"] == f"Tarjeta •••{tarjeta.ultimos_4}"


def test_contexto_referencia_menciona_tarjeta_sin_exponer_mas_que_ultimos_4(db, registrado):
    from sqlalchemy import select

    from app.genai.clasificador import _contexto_referencia
    from app.models import Queja, Tarjeta

    _, cliente_id, cuenta_id = registrado()
    tarjeta = db.scalar(select(Tarjeta).where(Tarjeta.cuenta_id == cuenta_id))
    queja = Queja(cliente_id=cliente_id, texto="x", tarjeta_id=tarjeta.tarjeta_id)
    db.add(queja)
    db.commit()

    contexto = _contexto_referencia(db, queja)
    assert tarjeta.ultimos_4 in contexto
    assert "Contexto adicional" in contexto


def test_sin_referencia_el_contexto_queda_vacio(db, registrado):
    from app.genai.clasificador import _contexto_referencia
    from app.models import Queja

    _, cliente_id, _ = registrado()
    queja = Queja(cliente_id=cliente_id, texto="x")
    db.add(queja)
    db.commit()

    assert _contexto_referencia(db, queja) == ""
