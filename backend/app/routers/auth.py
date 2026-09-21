from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import crear_token
from app.schemas.auth import LoginIn, RegistroIn, RegistroOut, TokenOut
from app.schemas.tarjetas import TarjetaOut
from app.services import auth as auth_service
from app.services import onboarding

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)):
    try:
        usuario = auth_service.autenticar(db, datos, ip=request.client.host if request.client else None)
    except auth_service.CredencialesInvalidas:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return TokenOut(access_token=crear_token(usuario.usuario_id, usuario.rol, usuario.cliente_id))


@router.post("/registro", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
def registro(datos: RegistroIn, request: Request, db: Session = Depends(get_db)):
    try:
        cliente, usuario, cuenta, tarjeta = onboarding.registrar(db, datos, ip=request.client.host if request.client else None)
    except onboarding.ClienteDuplicado as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"campo": e.campo, "mensaje": "Ya existe un cliente con ese dato"})
    return RegistroOut(
        access_token=crear_token(usuario.usuario_id, usuario.rol, cliente.cliente_id),
        cliente_id=cliente.cliente_id,
        codigo_cliente=cliente.codigo_cliente,
        cuenta_id=cuenta.cuenta_id,
        numero_cuenta=cuenta.numero_cuenta,
        segmento=cliente.segmento,
        tarjeta=TarjetaOut.model_validate(tarjeta),
    )
