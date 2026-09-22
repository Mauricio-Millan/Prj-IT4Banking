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
        categoria, confianza, motivo = "fraude", 0.9, "transaccion no reconocida"
    elif any(p in texto for p in ("tarjeta", "cuenta", "prestamo", "préstamo", "cobro", "comision", "comisión", "saldo")):
        categoria, confianza, motivo = "producto", 0.85, "problema con un producto"
    elif any(p in texto for p in ("atencion", "atención", "respondio", "respondió", "app", "canal", "cajero", "tiempo", "lento", "lenta")):
        categoria, confianza, motivo = "servicio", 0.8, "problema de atencion o canal"
    else:
        categoria, confianza, motivo = "otro", 0.5, "no clasificable con certeza"
    return json.dumps({"categoria": categoria, "confianza": confianza, "motivo": motivo, "senales": senales})


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
