import json
from datetime import date
from decimal import Decimal

from app.genai.clasificador import _es_reincidente, _validar_salida, calcular_prioridad
from app.genai.client import complete
from app.models import Cliente, Queja


# ---- _validar_salida (R1/R5/R15) ----

def test_validar_salida_json_valido():
    cruda = json.dumps({"categoria": "producto", "confianza": 0.8, "motivo": "x", "senales": {"vulnerabilidad": True}})
    categoria, confianza, senales = _validar_salida(cruda)
    assert categoria == "producto" and confianza == Decimal("0.8")
    assert senales == {"vulnerabilidad": True, "amenaza_escalamiento": False}


def test_validar_salida_json_invalido_no_deja_sugerencia():
    # distinto del fallback de "categoria fuera de lista": si ni siquiera es JSON, no hay
    # nada que rescatar (None), la queja queda sin categoria_sugerida en vez de forzar "otro".
    categoria, confianza, senales = _validar_salida("esto no es json")
    assert (categoria, confianza, senales) == (None, None, {})


def test_validar_salida_categoria_fuera_de_lista_cae_en_fallback():
    cruda = json.dumps({"categoria": "tarjeta", "confianza": 0.9, "senales": {}})  # taxonomia vieja
    categoria, confianza, senales = _validar_salida(cruda)
    assert (categoria, confianza) == ("otro", Decimal("0"))


def test_validar_salida_confianza_fuera_de_rango_cae_en_fallback():
    cruda = json.dumps({"categoria": "producto", "confianza": 1.5, "senales": {}})
    categoria, confianza, _ = _validar_salida(cruda)
    assert (categoria, confianza) == ("otro", Decimal("0"))


def test_validar_salida_senales_ausentes_se_tratan_como_false():
    cruda = json.dumps({"categoria": "servicio", "confianza": 0.7})  # sin "senales"
    categoria, confianza, senales = _validar_salida(cruda)
    assert categoria == "servicio"
    assert senales == {"vulnerabilidad": False, "amenaza_escalamiento": False}


def test_validar_salida_senales_mal_formadas_se_tratan_como_false():
    cruda = json.dumps({"categoria": "servicio", "confianza": 0.7, "senales": {"vulnerabilidad": "si"}})
    _, _, senales = _validar_salida(cruda)
    assert senales["vulnerabilidad"] is False  # "si" no es True


# ---- calcular_prioridad (V10/V12/V13/V14) ----

def test_prioridad_fraude_es_siempre_alta():
    assert calcular_prioridad("fraude", {}, reincidente=False) == "alta"


def test_prioridad_alta_por_senal_de_vulnerabilidad():
    assert calcular_prioridad("servicio", {"vulnerabilidad": True}, reincidente=False) == "alta"


def test_prioridad_alta_por_senal_de_escalamiento():
    assert calcular_prioridad("producto", {"amenaza_escalamiento": True}, reincidente=False) == "alta"


def test_prioridad_alta_por_reincidencia():
    assert calcular_prioridad("servicio", {}, reincidente=True) == "alta"


def test_prioridad_normal_sin_senales_ni_fraude_ni_reincidencia():
    assert calcular_prioridad("servicio", {}, reincidente=False) == "normal"


def test_prioridad_nunca_baja_por_una_senal_falsa():
    assert calcular_prioridad("otro", {"vulnerabilidad": False, "amenaza_escalamiento": False}, reincidente=False) == "normal"


# ---- _es_reincidente (V13, sin IA) ----

def test_es_reincidente_por_queja_pendiente_del_mismo_cliente(db):
    cliente_obj = Cliente(codigo_cliente="1234567895", tipo_documento="DNI", numero_documento="45872103",
                           nombres="Maria", apellidos="Q", fecha_nacimiento=date(1994, 3, 18),
                           email="reinc@correo.pe", region="Lima")
    db.add(cliente_obj)
    db.flush()
    vieja = Queja(cliente_id=cliente_obj.cliente_id, texto="una queja anterior con texto suficiente",
                  estado_revision="pendiente")
    nueva = Queja(cliente_id=cliente_obj.cliente_id, texto="una queja nueva con texto suficiente",
                  estado_revision="pendiente")
    db.add_all([vieja, nueva])
    db.commit()

    assert _es_reincidente(db, cliente_obj.cliente_id, "producto", nueva.queja_id) is True


def test_no_es_reincidente_sin_quejas_previas(db):
    cliente_obj = Cliente(codigo_cliente="1234567896", tipo_documento="DNI", numero_documento="45872104",
                           nombres="Jose", apellidos="R", fecha_nacimiento=date(1990, 1, 1),
                           email="sinquejas@correo.pe", region="Lima")
    db.add(cliente_obj)
    db.flush()
    unica = Queja(cliente_id=cliente_obj.cliente_id, texto="mi unica queja con texto suficiente",
                  estado_revision="pendiente")
    db.add(unica)
    db.commit()

    # excluye su propia queja_id: no deberia contarse a si misma como "pendiente" previa
    assert _es_reincidente(db, cliente_obj.cliente_id, "producto", unica.queja_id) is False


# ---- proveedor falso (determinista, sin red) ----

def test_proveedor_falso_es_deterministico_y_no_hace_red():
    r1, modelo1 = complete(system="sys", prompt="Hay un retiro que no reconozco")
    r2, _ = complete(system="sys", prompt="Hay un retiro que no reconozco")
    assert r1 == r2
    assert modelo1 == "falso-determinista"
    assert json.loads(r1)["categoria"] == "fraude"
