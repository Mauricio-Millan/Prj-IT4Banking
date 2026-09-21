from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models import AsientoContable, Cuenta, MovimientoContable


def _depositar(cliente, headers, numero_cuenta, monto):
    return cliente.post("/transacciones", headers=headers,
                         json={"tipo": "deposito", "monto": monto, "cuenta_destino": numero_cuenta, "canal": "agente"})


def _retirar(cliente, headers, cuenta_id, monto):
    return cliente.post("/transacciones", headers=headers,
                         json={"tipo": "retiro", "monto": monto, "cuenta_origen_id": cuenta_id, "canal": "cajero"})


def test_primeros_tres_retiros_del_mes_son_gratis(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "1000.00")

    for _ in range(3):
        r = _retirar(cliente, headers, cuenta_id, "100.00")
        assert r.status_code == 201, r.text
        assert r.json()["comision"] is None

    assert db.get(Cuenta, cuenta_id).saldo == Decimal("700.00")


def test_cuarto_retiro_paga_comision(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "1000.00")
    for _ in range(3):
        _retirar(cliente, headers, cuenta_id, "100.00")

    r = _retirar(cliente, headers, cuenta_id, "100.00")
    assert r.status_code == 201, r.text
    assert r.json()["comision"]["monto"] == "3.00"
    assert "4.º del mes" in r.json()["comision"]["concepto"]
    assert db.get(Cuenta, cuenta_id).saldo == Decimal("597.00")

    from app.models import Transaccion
    comision_tx = db.query(Transaccion).filter_by(tipo="comision").one()
    retiro_tx_id = r.json()["transaccion_id"]
    assert comision_tx.transaccion_origen_id == retiro_tx_id

    asiento = db.query(AsientoContable).filter_by(transaccion_id=comision_tx.transaccion_id).one()
    movs = db.query(MovimientoContable).filter_by(asiento_id=asiento.asiento_id).all()
    assert {(m.tipo_movimiento, m.importe) for m in movs} == {("D", Decimal("3.00")), ("H", Decimal("3.00"))}


def test_saldo_insuficiente_para_retiro_mas_comision(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "402.00")
    for _ in range(3):
        _retirar(cliente, headers, cuenta_id, "100.00")
    assert db.get(Cuenta, cuenta_id).saldo == Decimal("102.00")

    r = _retirar(cliente, headers, cuenta_id, "100.00")
    assert r.status_code == 422
    assert "comisión" in r.json()["detail"].lower()
    assert db.get(Cuenta, cuenta_id).saldo == Decimal("102.00")

    from app.models import Transaccion
    assert db.query(Transaccion).filter_by(tipo="comision").count() == 0


def test_cuota_gratis_se_reinicia_cada_mes(registrado, db):
    from app.models import Transaccion
    from app.services.comisiones import calcular

    _, _, cuenta_id = registrado()
    # 4 retiros "aplicados" en septiembre (mes anterior): agotarian la cuota gratis de ESE mes,
    # pero no deberian contar para octubre.
    for _ in range(4):
        db.add(Transaccion(cuenta_origen_id=cuenta_id, tipo="retiro", monto=Decimal("50.00"), canal="cajero",
                            estado="aplicada", fecha_hora=datetime(2026, 9, 15)))
    db.commit()

    tarifa, monto = calcular(db, "retiro", cuenta_id, date(2026, 10, 1))
    assert monto == Decimal("0.00")


def test_transferencia_intrabancaria_sin_comision(cliente, registrado, db):
    headers_a, _, cuenta_a = registrado()
    _, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")
    numero_a = db.get(Cuenta, cuenta_a).numero_cuenta
    numero_b = db.get(Cuenta, cuenta_b).numero_cuenta
    _depositar(cliente, headers_a, numero_a, "500.00")

    r = cliente.post("/transacciones", headers=headers_a,
                      json={"tipo": "transferencia", "monto": "100.00", "cuenta_origen_id": cuenta_a, "cuenta_destino": numero_b})
    assert r.status_code == 201, r.text
    assert r.json()["comision"] is None

    from app.models import Transaccion
    assert db.query(Transaccion).filter_by(tipo="comision").count() == 0


def test_penalidad_por_cuota_atrasada(cliente, registrado, db):
    from app.models import Cuota

    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]

    cuota1 = db.query(Cuota).filter_by(prestamo_id=prestamo_id, numero=1).one()
    dias_atraso = 12
    db.query(Cuota).filter_by(cuota_id=cuota1.cuota_id).update({
        "estado": "vencida", "fecha_vencimiento": date.today() - timedelta(days=dias_atraso),
    })
    db.commit()

    saldo_antes = db.get(Cuenta, cuenta_id).saldo
    pago = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert pago.status_code == 201, pago.text
    body = pago.json()
    assert body["penalidad"]["monto"] == "15.00"
    assert str(dias_atraso) in body["penalidad"]["concepto"]

    total_esperado = Decimal(body["cuota"]["total"]) + Decimal("15.00")
    assert Decimal(body["total_debitado"]) == total_esperado
    assert db.get(Cuenta, cuenta_id).saldo == saldo_antes - total_esperado

    from app.models import Transaccion
    comision_tx = db.query(Transaccion).filter_by(tipo="comision").one()
    assert comision_tx.transaccion_origen_id == body["transaccion_id"]


def test_cuota_al_dia_sin_penalidad(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    r = cliente.post("/prestamos/solicitudes", headers=headers,
                      json={"monto_original": "1000.00", "plazo": 12, "cuenta_id": cuenta_id})
    prestamo_id = r.json()["prestamo_id"]

    pago = cliente.post(f"/prestamos/{prestamo_id}/pagos", headers=headers, json={"cuenta_origen_id": cuenta_id})
    assert pago.status_code == 201, pago.text
    assert pago.json()["penalidad"] is None

    from app.models import Transaccion
    assert db.query(Transaccion).filter_by(tipo="comision").count() == 0


def test_tarifario_publico_no_expone_tarifa_inactiva(cliente):
    r = cliente.get("/tarifario")
    assert r.status_code == 200
    codigos = {t["codigo"] for t in r.json()["tarifas"]}
    assert codigos == {"RET-RED", "PRE-ATR", "TRF-INTRA", "MAN-CTA", "TAR-EMI"}
    assert "TRF-INTER" not in codigos
    assert "ITF" in r.json()["nota_itf"]


def test_comision_retiro_preview(cliente, registrado, db):
    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "1000.00")

    r = cliente.get(f"/cuentas/{cuenta_id}/comision-retiro", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"monto": "0.00", "retiros_gratis_restantes": 3}

    for _ in range(3):
        _retirar(cliente, headers, cuenta_id, "50.00")

    r2 = cliente.get(f"/cuentas/{cuenta_id}/comision-retiro", headers=headers)
    assert r2.json() == {"monto": "3.00", "retiros_gratis_restantes": 0}


def test_conciliacion_comisiones_igual_a_saldo_4101(cliente, registrado, db):
    from sqlalchemy import func, select

    from app.models.contabilidad import CODIGO_INGRESOS_COMISION, CuentaContable

    headers, _, cuenta_id = registrado()
    numero = db.get(Cuenta, cuenta_id).numero_cuenta
    _depositar(cliente, headers, numero, "1000.00")
    for _ in range(4):
        _retirar(cliente, headers, cuenta_id, "50.00")

    from app.models import Transaccion
    suma_comisiones = db.scalar(select(func.coalesce(func.sum(Transaccion.monto), 0)).where(
        Transaccion.tipo == "comision", Transaccion.estado == "aplicada",
    ))

    id_4101 = db.scalar(select(CuentaContable.cuenta_contable_id).where(CuentaContable.codigo == CODIGO_INGRESOS_COMISION))
    haber = db.scalar(select(func.coalesce(func.sum(MovimientoContable.importe), 0)).where(
        MovimientoContable.cuenta_contable_id == id_4101, MovimientoContable.tipo_movimiento == "H"))
    debe = db.scalar(select(func.coalesce(func.sum(MovimientoContable.importe), 0)).where(
        MovimientoContable.cuenta_contable_id == id_4101, MovimientoContable.tipo_movimiento == "D"))

    assert suma_comisiones == (haber - debe)
    assert suma_comisiones == Decimal("3.00")
