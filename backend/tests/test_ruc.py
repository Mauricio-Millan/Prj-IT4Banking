from app.core.ruc import ruc_valido

# RUC reales conocidos (SUNAT y un contribuyente publico), verificados manualmente con el
# algoritmo antes de usarlos como vector fijo — igual que se hizo con el DV Luhn de HU-Numeracion.
RUC_VALIDOS = ["20100070970", "20131312955"]


def test_ruc_validos_conocidos():
    for ruc in RUC_VALIDOS:
        assert ruc_valido(ruc)


def test_ruc_con_digito_verificador_incorrecto():
    valido = RUC_VALIDOS[0]
    invalido = valido[:-1] + str((int(valido[-1]) + 1) % 10)
    assert not ruc_valido(invalido)


def test_ruc_que_no_es_persona_juridica():
    # empieza en "10" (persona natural con negocio), no en "20"
    assert not ruc_valido("10131312955")


def test_ruc_con_longitud_incorrecta():
    assert not ruc_valido("2010007097")  # 10 digitos
    assert not ruc_valido("201000709700")  # 12 digitos


def test_ruc_no_numerico():
    assert not ruc_valido("2010007097A")
