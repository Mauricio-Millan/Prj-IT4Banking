from app.core.numeracion import cci_de, digito_verificador, generar_codigo_cliente, generar_numero_cuenta


def test_digito_verificador_valores_fijos():
    assert digito_verificador("45872103") == "2"
    assert digito_verificador("123456789") == "7"


def test_generar_codigo_cliente_10_digitos_dv_valido_y_no_empieza_en_cero():
    for _ in range(50):
        codigo = generar_codigo_cliente()
        assert len(codigo) == 10 and codigo.isdigit()
        assert codigo[0] != "0"
        assert digito_verificador(codigo[:-1]) == codigo[-1]


def test_generar_numero_cuenta_14_digitos_oficina_moneda_y_dv_valido():
    for moneda, digito_esperado in (("PEN", "1"), ("USD", "2")):
        cuenta = generar_numero_cuenta(moneda)
        assert len(cuenta) == 14 and cuenta.isdigit()
        assert cuenta.startswith("001" + digito_esperado)
        assert digito_verificador(cuenta[:-1]) == cuenta[-1]


def test_cci_es_determinista_20_digitos_y_contiene_la_cuenta():
    cuenta = generar_numero_cuenta("PEN")
    cci_1 = cci_de(cuenta)
    cci_2 = cci_de(cuenta)
    assert cci_1 == cci_2  # misma entrada -> mismo CCI
    assert len(cci_1) == 20 and cci_1.isdigit()
    assert cci_1.startswith("099001")
    # los 12 digitos centrales son la cuenta sin oficina, con un 0 a la izquierda
    assert cci_1[6:18] == "0" + cuenta[3:]
    dv1, dv2 = cci_1[18], cci_1[19]
    assert digito_verificador(cci_1[:6]) == dv1
    assert digito_verificador(cci_1[6:18]) == dv2


def test_unicidad_en_mil_generaciones():
    codigos = {generar_codigo_cliente() for _ in range(1000)}
    cuentas = {generar_numero_cuenta("PEN") for _ in range(1000)}
    ccis = {cci_de(c) for c in cuentas}
    assert len(codigos) == 1000 and len(cuentas) == 1000 and len(ccis) == 1000
