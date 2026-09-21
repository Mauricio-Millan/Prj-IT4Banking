from decimal import Decimal

from app.models import Cuenta, Prestamo


def test_solicitud_dentro_del_limite_sin_mora_queda_vigente(cliente, registrado, db):
    headers, _, cuenta_id = registrado()  # clasico: limite 15000, tasa 18.50
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "5000.00", "plazo": 12, "cuenta_id": cuenta_id})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "vigente"
    assert body["tasa"] == "18.50"
    assert body["fecha_desembolso"] is not None
    assert body["cuotas_total"] == 12
    assert body["cuenta_desembolso_numero"] == db.get(Cuenta, cuenta_id).numero_cuenta
    assert db.get(Cuenta, cuenta_id).saldo == Decimal("5000.00")


def test_solicitud_sobre_el_limite_queda_solicitado(cliente, registrado):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "20000.00", "plazo": 24, "cuenta_id": cuenta_id})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["estado"] == "solicitado"
    assert body["fecha_desembolso"] is None
    assert body["cuotas_total"] == 0


def test_solicitud_con_cuenta_ajena_da_404(cliente, registrado):
    headers_a, _, _ = registrado()
    _, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    r = cliente.post("/prestamos/solicitudes", headers=headers_a, json={"monto_original": "1000.00", "plazo": 6, "cuenta_id": cuenta_b})
    assert r.status_code == 404


def test_solicitud_con_mora_vigente_existente_es_rechazada(cliente, registrado, db):
    headers, cliente_id, cuenta_id = registrado()
    db.add(Prestamo(cliente_id=cliente_id, cuenta_desembolso_id=cuenta_id, monto_original=Decimal("3000"),
                     saldo_capital=Decimal("3000"), tasa=Decimal("18.50"), plazo=12, estado="vigente",
                     dias_mora=15, bucket_mora="1-30"))
    db.commit()

    r = cliente.post("/prestamos/solicitudes", headers=headers, json={"monto_original": "2000.00", "plazo": 6, "cuenta_id": cuenta_id})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "rechazado"


def test_lista_solo_prestamos_propios(cliente, registrado):
    headers_a, _, cuenta_a = registrado()
    headers_b, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/prestamos/solicitudes", headers=headers_a, json={"monto_original": "1000.00", "plazo": 6, "cuenta_id": cuenta_a})
    cliente.post("/prestamos/solicitudes", headers=headers_b, json={"monto_original": "2000.00", "plazo": 6, "cuenta_id": cuenta_b})

    r = cliente.get("/prestamos", headers=headers_a)
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["monto_original"] == "1000.00"


def test_cronograma_del_vector_de_la_hu(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]
    # la tasa la asigna el segmento (clasico=18.50%), no la del vector (12.6825%): se fuerza
    # a mano para poder comparar contra el vector documentado en la HU.
    db.query(Prestamo).filter_by(prestamo_id=prestamo_id).update({"tasa": Decimal("12.6825")})
    from app.services.prestamos import generar_cronograma
    from datetime import date
    filas = generar_cronograma(Decimal("1000.00"), Decimal("12.6825"), 12, date.today())
    assert len(filas) == 12
    assert filas[0]["interes"] == Decimal("10.00")
    assert filas[0]["capital"] == Decimal("78.85")
    assert filas[0]["saldo_capital_despues"] == Decimal("921.15")
    assert sum(f["capital"] for f in filas) == Decimal("1000.00")
    for f in filas:
        assert f["total"] == f["capital"] + f["interes"]


def test_pago_de_la_primera_cuota(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]
    cronograma = cliente.get(f"/prestamos/{prestamo_id}/cronograma", headers=headers).json()
    total_1 = Decimal(cronograma[0]["total"])
    capital_1 = Decimal(cronograma[0]["capital"])
    saldo_antes = db.get(Cuenta, cuenta_id).saldo  # ya tiene el desembolso acreditado

    pago = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert pago.status_code == 201, pago.text
    body = pago.json()
    assert body["cuota"]["numero"] == 1 and body["cuota"]["estado"] == "pagada"
    assert body["penalidad"] is None
    assert Decimal(body["total_debitado"]) == total_1
    assert Decimal(body["saldo_capital"]) == Decimal("1000.00") - capital_1
    assert db.get(Cuenta, cuenta_id).saldo == saldo_antes - total_1


def test_pago_con_saldo_insuficiente_no_cambia_nada(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]
    # se retira casi todo el desembolso para dejar saldo insuficiente para la cuota
    db.query(Cuenta).filter_by(cuenta_id=cuenta_id).update({"saldo": Decimal("1.00")})
    db.commit()

    pago = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert pago.status_code == 422
    assert db.get(Cuenta, cuenta_id).saldo == Decimal("1.00")

    cronograma = cliente.get(f"/prestamos/{prestamo_id}/cronograma", headers=headers).json()
    assert cronograma[0]["estado"] == "pendiente"


def test_pagar_prestamo_no_vigente_da_409(cliente, registrado):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "20000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]  # queda 'solicitado', no 'vigente'

    pago = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert pago.status_code == 409


def test_cronograma_y_pago_de_prestamo_ajeno_dan_404(cliente, registrado):
    headers_a, _, cuenta_a = registrado()
    headers_b, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    r = cliente.post("/prestamos/solicitudes", headers=headers_a,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_a})
    prestamo_id = r.json()["prestamo_id"]

    assert cliente.get(f"/prestamos/{prestamo_id}/cronograma", headers=headers_b).status_code == 404
    assert cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers_b,
                         json={"cuenta_origen_id": cuenta_b}).status_code == 404


def test_ultima_cuota_cancela_el_prestamo(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "500.00", "plazo": 2, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]
    # el desembolso solo acredita el capital (500.00); las cuotas cuestan capital+interes,
    # asi que hace falta un deposito extra para cubrir ambas.
    cliente.post("/transacciones", headers=headers,
                 json={"tipo": "deposito", "monto": "50.00", "cuenta_destino": db.get(Cuenta, cuenta_id).numero_cuenta, "canal": "agente"})

    cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    ultimo = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert ultimo.status_code == 201, ultimo.text
    assert ultimo.json()["saldo_capital"] == "0.00"
    assert ultimo.json()["estado_prestamo"] == "cancelado"
