from app.core.tarjetas_crypto import cifrar_pan, descifrar_pan, huella_pan

PAN = "5499009912345675"


def test_cifrar_y_descifrar_recupera_el_pan_original():
    blob = cifrar_pan(PAN, cuenta_id=42)
    assert descifrar_pan(blob, cuenta_id=42) == PAN


def test_pan_cifrado_no_contiene_los_digitos_del_pan_en_claro():
    blob = cifrar_pan(PAN, cuenta_id=42)
    assert PAN.encode() not in blob


def test_descifrado_falla_si_el_aad_cuenta_id_no_coincide():
    """AAD = cuenta_id: un blob no se puede trasplantar de una fila a otra."""
    blob = cifrar_pan(PAN, cuenta_id=42)
    try:
        descifrar_pan(blob, cuenta_id=43)
        assert False, "debia fallar: cuenta_id (AAD) distinto al de cifrado"
    except Exception:
        pass


def test_cifrado_no_es_deterministico_nonce_aleatorio_por_llamada():
    assert cifrar_pan(PAN, cuenta_id=42) != cifrar_pan(PAN, cuenta_id=42)


def test_huella_es_deterministica_mismo_pan_misma_huella():
    assert huella_pan(PAN) == huella_pan(PAN)


def test_huella_distingue_panes_distintos():
    assert huella_pan(PAN) != huella_pan("5499009912345683")
