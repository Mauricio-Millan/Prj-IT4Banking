from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def crear_token(usuario_id: int, rol: str, cliente_id: int | None) -> str:
    # Sesion corta para personal interno (V15): un JWT de backoffice filtrado o dejado
    # abierto expira 4 veces mas rapido que el de un cliente.
    minutos = settings.jwt_exp_minutes if rol == "cliente" else settings.jwt_exp_minutes_backoffice
    ahora = datetime.now(timezone.utc)
    claims = {
        "sub": str(usuario_id),
        "rol": rol,
        "cliente_id": cliente_id,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


@dataclass(frozen=True)
class UsuarioActual:
    usuario_id: int
    rol: str
    cliente_id: int | None


_bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UsuarioActual:
    # ponytail: sin lookup a Usuario por request — todo lo necesario ya esta en el JWT.
    # Si luego se necesita revocar sesiones al desactivar un usuario, agregar un check aqui.
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    try:
        claims = decodificar_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    return UsuarioActual(usuario_id=int(claims["sub"]), rol=claims["rol"], cliente_id=claims.get("cliente_id"))


def require_role(*roles: str):
    """Para roles internos (analista/admin) hace lookup a `usuario` en cada peticion — a
    diferencia de `get_current_user`, que confia ciegamente en el JWT. Esto es lo que hace
    que desactivar a alguien surta efecto de inmediato (V7) en vez de esperar a que expire
    el token, y lo que bloquea el resto del backoffice mientras debe_cambiar_password siga
    en 1 (V10). Las rutas de cliente no pagan este costo: get_current_user/require_cliente
    siguen sin tocar la base de datos."""

    def _dep(usuario: UsuarioActual = Depends(get_current_user), db: Session = Depends(get_db)) -> UsuarioActual:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No autorizado")

        if usuario.rol in ("analista", "admin"):
            from app.models import Usuario  # import tardio: evita ciclo security <-> models

            fila = db.get(Usuario, usuario.usuario_id)
            if fila is None or not fila.activo or fila.rol != usuario.rol:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")
            if fila.debe_cambiar_password:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail={"codigo": "CAMBIO_PASSWORD_REQUERIDO",
                            "mensaje": "Debes cambiar tu contraseña temporal antes de continuar"},
                )
        return usuario

    return _dep


def require_cliente(usuario: UsuarioActual = Depends(get_current_user)) -> int:
    """La mayoria de rutas de cliente necesitan su cliente_id, nunca el de la URL/body."""
    if usuario.cliente_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Ruta exclusiva de clientes")
    return usuario.cliente_id
