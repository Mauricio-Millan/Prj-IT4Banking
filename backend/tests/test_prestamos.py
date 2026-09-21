from decimal import Decimal

from app.models import Prestamo


def test_solicitud_dentro_del_limite_sin_mora_queda_vigente(cliente, registrado):
    headers, _, _ = registrado()  # clasico: limite 15000, tasa 18.50
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "5000.00", "plazo": 12})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "vigente"
    assert body["tasa"] == "18.50"
    assert body["fecha_desembolso"] is not None


def test_solicitud_sobre_el_limite_queda_solicitado(cliente, registrado):
    headers, _, _ = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "20000.00", "plazo": 24})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "solicitado"
    assert body["fecha_desembolso"] is None


def test_solicitud_con_mora_vigente_existente_es_rechazada(cliente, registrado, db):
    headers, cliente_id, _ = registrado()
    db.add(Prestamo(cliente_id=cliente_id, monto_original=Decimal("3000"), saldo_capital=Decimal("3000"),
                     tasa=Decimal("18.50"), plazo=12, estado="vigente", dias_mora=15, bucket_mora="1-30"))
    db.commit()

    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "2000.00", "plazo": 6})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "rechazado"


def test_lista_solo_prestamos_propios(cliente, registrado):
    headers_a, _, _ = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/prestamos/solicitudes", headers=headers_a, json={"monto_original": "1000.00", "plazo": 6})
    cliente.post("/prestamos/solicitudes", headers=headers_b, json={"monto_original": "2000.00", "plazo": 6})

    r = cliente.get("/prestamos", headers=headers_a)
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["monto_original"] == "1000.00"
