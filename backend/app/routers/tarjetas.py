from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import UsuarioActual, get_current_user, require_cliente
from app.schemas.tarjetas import RevelarIn, TarjetaOut, TarjetaRevelada
from app.services import tarjetas as tarjetas_service

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])


@router.get("", response_model=list[TarjetaOut])
def listar(db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    return tarjetas_service.listar(db, cliente_id)


@router.post("/{tarjeta_id}/revelar", response_model=TarjetaRevelada)
def revelar(
    tarjeta_id: int,
    datos: RevelarIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
    cliente_id: int = Depends(require_cliente),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return tarjetas_service.revelar(
            db, cliente_id, usuario.usuario_id, tarjeta_id, datos.password,
            ip=request.client.host if request.client else None,
        )
    except tarjetas_service.CredencialesInvalidas:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    except tarjetas_service.TarjetaNoActiva:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="La tarjeta no está activa")
    except tarjetas_service.DemasiadosIntentos:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos, espera 15 minutos")
