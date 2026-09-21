from decimal import Decimal

from app.core.numeracion import generar_numero_cuenta
from app.models import Cuenta


def _saldo(cliente, headers, cuenta_id):
    return Decimal(cliente.get(f"/cuentas/{cuenta_id}/saldo", headers=headers).json()["saldo"])


def _numero(db, cuenta_id):
    return db.get(Cuenta, cuenta_id).numero_cuenta


def test_deposito_suma_monto_exacto(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "deposito", "monto": "150.75", "cuenta_destino": _numero(db, cuenta_id), "canal": "agente"})
    assert r.status_code == 201, r.text
    assert r.json()["monto"] == "150.75"
    assert _saldo(cliente, headers, cuenta_id) == Decimal("150.75")


def test_deposito_sin_canal_da_422(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "deposito", "monto": "150.75", "cuenta_destino": _numero(db, cuenta_id)})
    assert r.status_code == 422


def test_retiro_resta_monto_exacto(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    cliente.post("/transacciones", headers=headers,
                 json={"tipo": "deposito", "monto": "100.00", "cuenta_destino": _numero(db, cuenta_id), "canal": "agente"})
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "retiro", "monto": "30.00", "cuenta_origen_id": cuenta_id, "canal": "cajero"})
    assert r.status_code == 201, r.text
    assert _saldo(cliente, headers, cuenta_id) == Decimal("70.00")


def test_retiro_con_saldo_insuficiente_no_modifica_nada(cliente, registrado):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "retiro", "monto": "10.00", "cuenta_origen_id": cuenta_id, "canal": "cajero"})
    assert r.status_code == 422
    assert _saldo(cliente, headers, cuenta_id) == Decimal("0")


def test_transferencia_mueve_monto_exacto_entre_cuentas(cliente, registrado, db):
    headers_a, _, cuenta_a = registrado()
    headers_b, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "deposito", "monto": "500.00", "cuenta_destino": _numero(db, cuenta_a), "canal": "agente"})

    r = cliente.post("/transacciones", headers=headers_a,
                      json={"tipo": "transferencia", "monto": "199.99",
                            "cuenta_origen_id": cuenta_a, "cuenta_destino": _numero(db, cuenta_b)})
    assert r.status_code == 201, r.text
    assert _saldo(cliente, headers_a, cuenta_a) == Decimal("300.01")
    assert _saldo(cliente, headers_b, cuenta_b) == Decimal("199.99")


def test_transferencia_entre_monedas_distintas_rechazada(cliente, registrado, db):
    from app.core.numeracion import cci_de

    headers_a, cliente_a, cuenta_a = registrado()
    _, cliente_b, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    numero_usd = generar_numero_cuenta("USD")
    cuenta_usd = Cuenta(cliente_id=cliente_b, tipo_cuenta="ahorro", moneda="USD", saldo=0,
                         numero_cuenta=numero_usd, cci=cci_de(numero_usd))
    db.add(cuenta_usd)
    db.commit()

    cliente.post("/transacciones", headers=headers_a,
                 json={"tipo": "deposito", "monto": "500.00", "cuenta_destino": _numero(db, cuenta_a), "canal": "agente"})
    r = cliente.post("/transacciones", headers=headers_a,
                      json={"tipo": "transferencia", "monto": "50.00",
                            "cuenta_origen_id": cuenta_a, "cuenta_destino": numero_usd})
    assert r.status_code == 422
    assert _saldo(cliente, headers_a, cuenta_a) == Decimal("500.00")


def test_transferencia_a_cuenta_inexistente_da_404(cliente, registrado, db):
    headers, _, cuenta_a = registrado()
    cliente.post("/transacciones", headers=headers,
                 json={"tipo": "deposito", "monto": "500.00", "cuenta_destino": _numero(db, cuenta_a), "canal": "agente"})
    r = cliente.post("/transacciones", headers=headers,
                      json={"tipo": "transferencia", "monto": "50.00",
                            "cuenta_origen_id": cuenta_a, "cuenta_destino": generar_numero_cuenta("PEN")})
    assert r.status_code == 404


def test_no_puede_operar_cuenta_origen_ajena(cliente, registrado):
    _, _, cuenta_a = registrado()
    headers_b, _, _ = registrado(numero_documento="70011223", email="otra@correo.pe")
    r = cliente.post("/transacciones", headers=headers_b,
                      json={"tipo": "retiro", "monto": "1.00", "cuenta_origen_id": cuenta_a, "canal": "cajero"})
    assert r.status_code == 404
