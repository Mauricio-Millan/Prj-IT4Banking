"""Tests unitarios de flows/calidad.py con DataFrames fijos -- sin base de datos (DoD de
HU-Pipeline-ETL-Bronze-Silver). Cada test aisla una sola regla de la tabla de la HU."""
from datetime import datetime, timedelta

import pandas as pd

from flows import calidad


def _df_transaccion(**overrides) -> pd.DataFrame:
    base = {
        "transaccion_id": 1, "cuenta_origen_id": 10, "cuenta_destino_id": 20,
        "fecha_hora": datetime.utcnow() - timedelta(hours=1), "tipo": "transferencia",
        "monto": 100.0, "canal": "web", "estado": "aplicada", "concepto": None,
        "transaccion_origen_id": None,
    }
    base.update(overrides)
    return pd.DataFrame([base])


IDS_CUENTA = {10, 20}


def test_transaccion_monto_no_positivo_se_rechaza():
    df = _df_transaccion(monto=0)
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert validas.empty
    assert rechazos[0]["regla"] == "monto_positivo"


def test_transaccion_id_duplicado_conserva_la_primera():
    df = pd.concat([_df_transaccion(monto=100), _df_transaccion(monto=200)], ignore_index=True)
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert len(validas) == 1
    assert validas.iloc[0]["monto"] == 100
    assert any(r["regla"] == "id_unico" for r in rechazos)


def test_transaccion_cuenta_origen_inexistente_se_rechaza():
    df = _df_transaccion(cuenta_origen_id=999)
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert validas.empty
    assert rechazos[0]["regla"] == "cuenta_origen_existe"


def test_transaccion_cuenta_destino_inexistente_se_rechaza():
    df = _df_transaccion(cuenta_destino_id=999)
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert validas.empty
    assert rechazos[0]["regla"] == "cuenta_destino_existe"


def test_transaccion_fecha_futura_se_rechaza():
    df = _df_transaccion(fecha_hora=datetime.utcnow() + timedelta(days=1))
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert validas.empty
    assert rechazos[0]["regla"] == "fecha_no_futura"


def test_transaccion_canal_fuera_de_dominio_se_rechaza():
    df = _df_transaccion(canal="bitcoin")
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert validas.empty
    assert rechazos[0]["regla"] == "canal_valido"


def test_transaccion_valida_no_se_rechaza():
    df = _df_transaccion()
    validas, rechazos = calidad.validar_transacciones(df, IDS_CUENTA)
    assert len(validas) == 1
    assert rechazos == []


def test_cuenta_moneda_fuera_de_dominio_se_rechaza():
    df = pd.DataFrame([{"cuenta_id": 1, "moneda": "EUR"}])
    validas, rechazos = calidad.validar_cuentas(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "moneda_valida"


def test_prestamo_dias_mora_negativo_se_rechaza():
    df = pd.DataFrame([{"prestamo_id": 1, "dias_mora": -1, "saldo_capital": 100.0}])
    validas, rechazos = calidad.validar_prestamos(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "dias_mora_no_negativo"


def test_prestamo_saldo_capital_negativo_se_rechaza():
    df = pd.DataFrame([{"prestamo_id": 1, "dias_mora": 0, "saldo_capital": -50.0}])
    validas, rechazos = calidad.validar_prestamos(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "saldo_capital_no_negativo"


def test_cuota_total_distinto_de_capital_mas_interes_se_rechaza():
    df = pd.DataFrame([{"cuota_id": 1, "capital": 78.85, "interes": 10.00, "total": 999.99}])
    validas, rechazos = calidad.validar_cuotas(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "total_igual_capital_mas_interes"


def test_cuota_total_correcto_no_se_rechaza():
    df = pd.DataFrame([{"cuota_id": 1, "capital": 78.85, "interes": 10.00, "total": 88.85}])
    validas, rechazos = calidad.validar_cuotas(df)
    assert len(validas) == 1
    assert rechazos == []


def test_movimiento_importe_no_positivo_se_rechaza():
    df = pd.DataFrame([{"movimiento_id": 1, "importe": 0.0, "tipo_movimiento": "D"}])
    validas, rechazos = calidad.validar_movimientos(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "importe_positivo"


def test_movimiento_tipo_fuera_de_dominio_se_rechaza():
    df = pd.DataFrame([{"movimiento_id": 1, "importe": 10.0, "tipo_movimiento": "X"}])
    validas, rechazos = calidad.validar_movimientos(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "tipo_movimiento_valido"


def test_cliente_region_fuera_de_lista_oficial_se_rechaza():
    df = pd.DataFrame([{"cliente_id": 1, "region": "Atlantida", "tipo_documento": "DNI", "razon_social": None}])
    validas, rechazos = calidad.validar_clientes(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "region_oficial"


def test_cliente_ruc_sin_razon_social_se_rechaza():
    df = pd.DataFrame([{"cliente_id": 1, "region": "Lima", "tipo_documento": "RUC", "razon_social": None}])
    validas, rechazos = calidad.validar_clientes(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "razon_social_segun_tipo_documento"


def test_cliente_dni_con_razon_social_se_rechaza():
    df = pd.DataFrame([{"cliente_id": 1, "region": "Lima", "tipo_documento": "DNI", "razon_social": "Acme SAC"}])
    validas, rechazos = calidad.validar_clientes(df)
    assert validas.empty
    assert rechazos[0]["regla"] == "razon_social_segun_tipo_documento"


def test_cliente_valido_no_se_rechaza():
    df = pd.DataFrame([{"cliente_id": 1, "region": "Lima", "tipo_documento": "DNI", "razon_social": None}])
    validas, rechazos = calidad.validar_clientes(df)
    assert len(validas) == 1
    assert rechazos == []


def test_advertencia_volumen_cero():
    assert calidad.advertencia_volumen(pd.DataFrame(columns=["monto"])) is not None


def test_advertencia_volumen_con_datos_es_none():
    assert calidad.advertencia_volumen(_df_transaccion()) is None


def test_validar_agrega_rechazos_de_todas_las_tablas():
    crudo = {
        "transaccion": _df_transaccion(monto=0),
        "cuenta": pd.DataFrame([{"cuenta_id": 10, "moneda": "PEN"}, {"cuenta_id": 20, "moneda": "PEN"}]),
        "prestamo": pd.DataFrame([{"prestamo_id": 1, "dias_mora": -1, "saldo_capital": 10.0}]),
        "cuota": pd.DataFrame([{"cuota_id": 1, "capital": 1.0, "interes": 1.0, "total": 3.0}]),
        "cliente": pd.DataFrame([{"cliente_id": 1, "region": "Lima", "tipo_documento": "DNI", "razon_social": None}]),
        "movimiento_contable": pd.DataFrame([{"movimiento_id": 1, "importe": 5.0, "tipo_movimiento": "D"}]),
    }
    validas, rechazos = calidad.validar(crudo)
    assert len(rechazos) == 3  # transaccion (monto), prestamo (dias_mora), cuota (total)
    assert set(rechazos["tabla"]) == {"transaccion", "prestamo", "cuota"}
    assert len(validas["cliente"]) == 1
    assert len(validas["movimiento_contable"]) == 1
