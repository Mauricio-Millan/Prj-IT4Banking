from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def crear_token(usuario_id: int, rol: str, cliente_id: int | None) -> str:
    ahora = datetime.now(timezone.utc)
    claims = {
        "sub": str(usuario_id),
        "rol": rol,
        "cliente_id": cliente_id,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.jwt_exp_minutes),
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
    def _dep(usuario: UsuarioActual = Depends(get_current_user)) -> UsuarioActual:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No autorizado")
        return usuario

    return _dep


def require_cliente(usuario: UsuarioActual = Depends(get_current_user)) -> int:
    """La mayoria de rutas de cliente necesitan su cliente_id, nunca el de la URL/body."""
    if usuario.cliente_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Ruta exclusiva de clientes")
    return usuario.cliente_id
