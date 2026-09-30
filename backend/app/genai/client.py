"""Strategy por configuracion (un `if`, no una jerarquia de clases) — ver
Plan-Maestro-Desarrollo.md §6/§11.1. 'falso' es el unico proveedor que corre en CI: nunca una
llamada de red real en los tests (LLM_PROVIDER=falso por defecto en .env.example y en conftest)."""
import json
import re

import httpx

from app.core.config import settings

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_RE_QUEJA = re.compile(r"<queja>(.*)</queja>", re.DOTALL)


def complete(system: str, prompt: str) -> tuple[str, str]:
    """Devuelve (respuesta_cruda, modelo)."""
    if settings.llm_provider == "falso":
        return _completar_falso(prompt), "falso-determinista"
    if settings.llm_provider == "groq":
        return _completar_groq(system, prompt), settings.llm_modelo
    raise RuntimeError(f"LLM_PROVIDER desconocido: {settings.llm_provider!r}")


def _completar_falso(prompt: str) -> str:
    """Determinista a partir de palabras clave del texto de la queja — SOLO el contenido entre
    <queja></queja>, nunca el prompt completo: la guia de categorias en las instrucciones ya
    menciona 'fraude'/'clonada'/'phishing' como parte del propio texto de instrucciones, y
    buscar en el prompt entero clasificaria cualquier queja como fraude por accidente."""
    match = _RE_QUEJA.search(prompt)
    texto = (match.group(1) if match else prompt).lower()
    senales = {
        "vulnerabilidad": any(p in texto for p in ("adulto mayor", "discapacidad", "embarazad")),
        "amenaza_escalamiento": any(p in texto for p in ("indecopi", "denuncia", "abogado", "redes sociales", "prensa")),
    }
    if any(p in texto for p in ("no reconozco", "no reconoce", "fraude", "clonada", "suplantacion", "suplantación", "phishing")):
        categoria, confianza, resumen = "fraude", 0.9, "El cliente reporta una transaccion que no reconoce. Podria tratarse de fraude o uso indebido de sus medios de pago."
    elif any(p in texto for p in ("tarjeta", "cuenta", "prestamo", "préstamo", "cobro", "comision", "comisión", "saldo")):
        categoria, confianza, resumen = "producto", 0.85, "El cliente reporta un problema con un producto (cuenta, tarjeta o prestamo). Pide que se revise y corrija."
    elif any(p in texto for p in ("atencion", "atención", "respondio", "respondió", "app", "canal", "cajero", "tiempo", "lento", "lenta")):
        categoria, confianza, resumen = "servicio", 0.8, "El cliente reporta un problema de atencion o de un canal digital. Pide una mejor experiencia de servicio."
    else:
        categoria, confianza, resumen = "otro", 0.5, "No fue posible clasificar el caso con certeza a partir del texto disponible."
    return json.dumps({"categoria": categoria, "confianza": confianza, "resumen": resumen, "senales": senales})


def _completar_groq(system: str, prompt: str) -> str:
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY no configurada: requerida para LLM_PROVIDER='groq'")
    respuesta = httpx.post(
        _GROQ_URL,
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": settings.llm_modelo,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        },
        timeout=15,
    )
    respuesta.raise_for_status()
    return respuesta.json()["choices"][0]["message"]["content"]
