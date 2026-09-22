from app.genai.masking import enmascarar


def test_enmascara_documento():
    assert enmascarar("Mi DNI es 45872103 y necesito ayuda") == "Mi DNI es [DOC] y necesito ayuda"


def test_enmascara_email():
    assert enmascarar("Mi correo es maria.quispe@correo.pe") == "Mi correo es [EMAIL]"


def test_enmascara_telefono():
    assert enmascarar("Mi celular es 987214550") == "Mi celular es [TEL]"
    assert enmascarar("Llamenme al +51 987 214 550") == "Llamenme al [TEL]"


def test_enmascara_numero_de_cuenta_largo():
    assert enmascarar("Mi cuenta es 00110384726119") == "Mi cuenta es [NUMERO]"


def test_enmascara_varios_a_la_vez():
    texto = "Soy Maria, DNI 45872103, correo maria@correo.pe, cel 987214550, cuenta 00110384726119"
    resultado = enmascarar(texto)
    assert "45872103" not in resultado
    assert "maria@correo.pe" not in resultado
    assert "987214550" not in resultado
    assert "00110384726119" not in resultado
    assert "[DOC]" in resultado and "[EMAIL]" in resultado and "[TEL]" in resultado and "[NUMERO]" in resultado


def test_texto_sin_pii_no_cambia():
    assert enmascarar("La aplicación se cierra sola al pagar") == "La aplicación se cierra sola al pagar"


def test_no_enmascara_numeros_cortos_como_montos():
    # un monto de 3-4 cifras (ej. "88.85" o "500") no debe caer en ningun patron de PII
    assert enmascarar("Me cobraron 500 soles de mas") == "Me cobraron 500 soles de mas"
