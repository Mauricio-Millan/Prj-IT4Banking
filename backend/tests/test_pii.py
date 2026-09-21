from app.core.pii import enmascarar_documento, enmascarar_email, enmascarar_telefono


def test_enmascarar_documento_deja_solo_los_ultimos_4():
    assert enmascarar_documento("45872103") == "****2103"


def test_enmascarar_documento_mas_corto_que_4_queda_todo_asterisco():
    assert enmascarar_documento("123") == "***"


def test_enmascarar_documento_none_es_none():
    assert enmascarar_documento(None) is None


def test_enmascarar_email():
    assert enmascarar_email("mf.quispe@correo.pe") == "m***@correo.pe"


def test_enmascarar_email_none_es_none():
    assert enmascarar_email(None) is None


def test_enmascarar_telefono_conserva_espacios_y_signo_mas():
    assert enmascarar_telefono("+51 987 214 550") == "+** *** *** 550"


def test_enmascarar_telefono_none_es_none():
    assert enmascarar_telefono(None) is None
