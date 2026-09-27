"""Tests unitarios de flows/analitica.py con DataFrames fijos -- sin SQL Server (DoD de
HU-Analitica-DW-PowerBI)."""
import pandas as pd

from flows import analitica


def test_construir_dim_cliente_persona_natural_es_empresa_false():
    df = pd.DataFrame([{
        "cliente_id": 1, "codigo_cliente": "1234567890", "iniciales": "M. T.", "documento_hash": "x" * 64,
        "ruc": None, "razon_social": None, "segmento": "joven", "region": "Lima",
        "fecha_alta": "2026-01-01", "estado": "activo",
    }])
    out = analitica.construir_dim_cliente(df)
    assert out.iloc[0]["es_empresa"] == False  # noqa: E712


def test_construir_dim_cliente_empresa_es_empresa_true():
    df = pd.DataFrame([{
        "cliente_id": 2, "codigo_cliente": "9999999999", "iniciales": "J. P.", "documento_hash": None,
        "ruc": "20100070970", "razon_social": "Acme SAC", "segmento": "empresa", "region": "Lima",
        "fecha_alta": "2026-01-01", "estado": "activo",
    }])
    out = analitica.construir_dim_cliente(df)
    assert out.iloc[0]["es_empresa"] == True  # noqa: E712


def test_hecho_transaccion_filtra_no_aplicadas():
    df_tx = pd.DataFrame([
        {"transaccion_id": 1, "cuenta_origen_id": 10, "cuenta_destino_id": None, "fecha_hora": "2026-09-18 10:00:00",
         "tipo": "retiro", "monto": 50.0, "canal": "web", "estado": "aplicada", "concepto": None, "transaccion_origen_id": None},
        {"transaccion_id": 2, "cuenta_origen_id": 10, "cuenta_destino_id": None, "fecha_hora": "2026-09-18 11:00:00",
         "tipo": "retiro", "monto": 30.0, "canal": "web", "estado": "rechazada", "concepto": None, "transaccion_origen_id": None},
    ])
    df_cuenta = pd.DataFrame([{"cuenta_id": 10, "cliente_id": 100}])
    out = analitica.construir_hecho_transaccion(df_tx, df_cuenta)
    assert len(out) == 1
    assert out.iloc[0]["transaccion_id"] == 1


def test_hecho_transaccion_cliente_id_desde_destino_si_no_hay_origen():
    df_tx = pd.DataFrame([{
        "transaccion_id": 1, "cuenta_origen_id": None, "cuenta_destino_id": 20, "fecha_hora": "2026-09-18 09:00:00",
        "tipo": "deposito", "monto": 100.0, "canal": "cajero", "estado": "aplicada", "concepto": None, "transaccion_origen_id": None,
    }])
    df_cuenta = pd.DataFrame([{"cuenta_id": 20, "cliente_id": 200}])
    out = analitica.construir_hecho_transaccion(df_tx, df_cuenta)
    assert out.iloc[0]["cliente_id"] == 200
    assert out.iloc[0]["canal_id"] == analitica.CANAL_A_ID["cajero"]


def test_hecho_cartera_diaria_copia_mora_tal_cual_y_cuenta_cuotas():
    df_prestamo = pd.DataFrame([{"prestamo_id": 1, "cliente_id": 5, "saldo_capital": 900.0, "dias_mora": 12, "bucket_mora": "1-30"}])
    df_cuota = pd.DataFrame([
        {"prestamo_id": 1, "estado": "pagada"},
        {"prestamo_id": 1, "estado": "pagada"},
        {"prestamo_id": 1, "estado": "vencida"},
        {"prestamo_id": 1, "estado": "pendiente"},
    ])
    out = analitica.construir_hecho_cartera_diaria(df_prestamo, df_cuota, __import__("datetime").date(2026, 9, 18))
    fila = out.iloc[0]
    assert fila["dias_mora"] == 12
    assert fila["bucket_mora"] == "1-30"
    assert fila["cuotas_pagadas"] == 2
    assert fila["cuotas_vencidas"] == 1
    assert fila["producto_id"] == analitica.PRODUCTO_PRESTAMO


def test_hecho_cartera_diaria_sin_prestamos_da_dataframe_vacio():
    out = analitica.construir_hecho_cartera_diaria(pd.DataFrame(), pd.DataFrame(), __import__("datetime").date(2026, 9, 18))
    assert out.empty


def test_rentabilidad_comision_se_atribuye_a_la_cuenta_que_pago():
    df_mov = pd.DataFrame([{
        "movimiento_id": 1, "transaccion_id": 1, "codigo_cuenta_contable": "4101", "tipo_movimiento": "H",
        "importe": 3.0, "fecha_contable": "2026-09-18",
    }])
    df_tx = pd.DataFrame([{"transaccion_id": 1, "tipo": "comision", "cuenta_origen_id": 10}])
    df_cuenta = pd.DataFrame([{"cuenta_id": 10, "cliente_id": 100, "tipo_cuenta": "ahorro"}])
    df_cliente = pd.DataFrame([{"cliente_id": 100, "segmento": "joven"}])

    out = analitica.construir_rentabilidad_mensual(df_mov, df_tx, df_cuenta, df_cliente)
    fila = out.iloc[0]
    assert fila["producto_id"] == analitica.PRODUCTO_AHORRO
    assert fila["segmento"] == "joven"
    assert fila["anio_mes"] == "2026-09"
    assert fila["ingresos"] == 3.0
    assert fila["costo"] == 0
    assert fila["margen"] == 3.0


def test_rentabilidad_interes_de_prestamo_se_atribuye_a_producto_prestamo():
    df_mov = pd.DataFrame([{
        "movimiento_id": 1, "transaccion_id": 1, "codigo_cuenta_contable": "4201", "tipo_movimiento": "H",
        "importe": 10.0, "fecha_contable": "2026-09-18",
    }])
    df_tx = pd.DataFrame([{"transaccion_id": 1, "tipo": "pago_prestamo", "cuenta_origen_id": 10}])
    df_cuenta = pd.DataFrame([{"cuenta_id": 10, "cliente_id": 100, "tipo_cuenta": "ahorro"}])
    df_cliente = pd.DataFrame([{"cliente_id": 100, "segmento": "clasico"}])

    out = analitica.construir_rentabilidad_mensual(df_mov, df_tx, df_cuenta, df_cliente)
    assert out.iloc[0]["producto_id"] == analitica.PRODUCTO_PRESTAMO


def test_rentabilidad_ignora_movimientos_debe_de_cuentas_de_ingreso():
    # el lado D de una comision (contra la cuenta del cliente) no debe contarse como ingreso
    df_mov = pd.DataFrame([{
        "movimiento_id": 1, "transaccion_id": 1, "codigo_cuenta_contable": "4101", "tipo_movimiento": "D",
        "importe": 3.0, "fecha_contable": "2026-09-18",
    }])
    df_tx = pd.DataFrame([{"transaccion_id": 1, "tipo": "comision", "cuenta_origen_id": 10}])
    df_cuenta = pd.DataFrame([{"cuenta_id": 10, "cliente_id": 100, "tipo_cuenta": "ahorro"}])
    df_cliente = pd.DataFrame([{"cliente_id": 100, "segmento": "joven"}])

    out = analitica.construir_rentabilidad_mensual(df_mov, df_tx, df_cuenta, df_cliente)
    assert out.empty


def test_rentabilidad_sin_movimientos_da_dataframe_vacio():
    vacio = pd.DataFrame(columns=["movimiento_id", "transaccion_id", "codigo_cuenta_contable", "tipo_movimiento", "importe", "fecha_contable"])
    out = analitica.construir_rentabilidad_mensual(vacio, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert out.empty
