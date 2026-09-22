"""R4: el texto de una queja nunca sale del backend sin enmascarar. Funcion pura, regex sobre
texto libre — no necesita ser perfecta, solo evitar que un DNI/correo/telefono/numero de cuenta
identificable viaje a un proveedor externo. Orden de aplicacion importa: telefono (9 digitos)
y numero largo (13-20) se enmascaran ANTES que documento (8-12), o el documento se comeria
un telefono/numero de cuenta que caiga dentro de su propio rango de longitud."""
import re

_RE_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_RE_TELEFONO = re.compile(r"(\+?51[\s-]?)?9\d{2}[\s-]?\d{3}[\s-]?\d{3}\b")
_RE_NUMERO_LARGO = re.compile(r"\b\d{13,20}\b")
_RE_DOCUMENTO = re.compile(r"\b\d{8,12}\b")


def enmascarar(texto: str) -> str:
    t = _RE_EMAIL.sub("[EMAIL]", texto)
    t = _RE_TELEFONO.sub("[TEL]", t)
    t = _RE_NUMERO_LARGO.sub("[NUMERO]", t)
    t = _RE_DOCUMENTO.sub("[DOC]", t)
    return t
