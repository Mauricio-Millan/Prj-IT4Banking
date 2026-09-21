"""Numeracion bancaria: codigo de cliente, numero de cuenta y CCI, todos con digito
verificador Luhn. Aleatorio + UNIQUE (no correlativo con SEQUENCE) a proposito: un SEQUENCE
de SQL Server no existe en SQLite (lo que usan los tests, ver tests/conftest.py) y derivar
el numero del IDENTITY obligaria a insertar con la columna en NULL y rellenarla despues.
Colision en un espacio de 10^9 con cientos de registros es despreciable; se comprueba con un
SELECT antes de usar el numero (services/onboarding.py) y el indice UNIQUE queda como ultima guarda.
"""
import secrets

from app.core.config import settings


def digito_verificador(cuerpo: str) -> str:
    suma = 0
    for i, ch in enumerate(reversed(cuerpo)):
        d = int(ch) * (2 if i % 2 == 0 else 1)
        suma += d - 9 if d > 9 else d
    return str((10 - suma % 10) % 10)


def generar_codigo_cliente() -> str:
    """10 digitos: 9 aleatorios (el primero != 0) + 1 DV."""
    cuerpo = str(secrets.randbelow(9 * 10**8) + 10**8)
    return cuerpo + digito_verificador(cuerpo)


def generar_numero_cuenta(moneda: str) -> str:
    """14 digitos: '001' oficina + 1 digito de moneda (PEN=1, USD=2) + 9 aleatorios + 1 DV."""
    digito_moneda = "1" if moneda == "PEN" else "2"
    aleatorios = f"{secrets.randbelow(10**9):09d}"
    cuerpo = f"{settings.oficina}{digito_moneda}{aleatorios}"
    return cuerpo + digito_verificador(cuerpo)


def cci_de(numero_cuenta: str) -> str:
    """20 digitos: 3 banco + 3 oficina + 12 cuenta (numero_cuenta sin oficina, con un 0 a la
    izquierda) + 2 DV. DV1 sobre los 6 primeros (banco+oficina), DV2 sobre los 12 de cuenta."""
    cuenta_sin_oficina = "0" + numero_cuenta[len(settings.oficina):]  # 11 -> 12 digitos
    banco_oficina = settings.banco_codigo_cce + settings.oficina
    dv1 = digito_verificador(banco_oficina)
    dv2 = digito_verificador(cuenta_sin_oficina)
    return banco_oficina + cuenta_sin_oficina + dv1 + dv2
