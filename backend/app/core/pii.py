"""Enmascarado de PII para respuestas de backoffice (Ley 29733, minimizacion de datos).
Funciones puras, aplicadas en la frontera HTTP via field_serializer en los schemas de
backoffice: el service sigue devolviendo objetos completos, nunca se enmascara antes de ahi.
"""


def enmascarar_documento(documento: str | None) -> str | None:
    """Solo los ultimos 4; el resto '*' con la misma longitud. Mas corto que 4 -> todo '*'."""
    if documento is None:
        return None
    if len(documento) <= 4:
        return "*" * len(documento)
    return "*" * (len(documento) - 4) + documento[-4:]


def enmascarar_email(email: str | None) -> str | None:
    """Primer caracter del usuario + '***' + '@' + dominio completo."""
    if email is None:
        return None
    usuario, arroba, dominio = email.partition("@")
    if not arroba:
        return "*" * len(email)
    return f"{usuario[:1]}***@{dominio}"


def enmascarar_telefono(telefono: str | None) -> str | None:
    """Solo los ultimos 3 digitos; el resto '*'. Espacios y '+' se conservan tal cual."""
    if telefono is None:
        return None
    total_digitos = sum(ch.isdigit() for ch in telefono)
    vistos = 0
    resultado = []
    for ch in telefono:
        if ch.isdigit():
            vistos += 1
            resultado.append(ch if total_digitos - vistos < 3 else "*")
        else:
            resultado.append(ch)
    return "".join(resultado)
