import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "secreto-de-pruebas"
# 32 bytes en base64, fijas para que los tests sean deterministas. Sin valor real: no hay
# datos de produccion en juego, ver app/core/config.py (sin default a proposito).
os.environ["TARJETA_CLAVE_CIFRADO"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
os.environ["TARJETA_CLAVE_HMAC"] = "OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OTk="

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.security import crear_token, hash_password
from app.main import app
from app.models import Base, CuentaContable, Usuario
from app.models.contabilidad import filas_seed_plan_de_cuentas

MARIA = {
    "tipo_documento": "DNI",
    "numero_documento": "45872103",
    "nombres": "maría fernanda",
    "apellidos": "quispe loayza",
    "fecha_nacimiento": "1994-03-18",
    "email": "MF.Quispe@correo.pe",
    "telefono": "+51 987 214 550",
    "region": "Arequipa",
    "password": "ClaveSegura1",
}


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        s.add_all(CuentaContable(**fila) for fila in filas_seed_plan_de_cuentas())
        s.commit()
        yield s


@pytest.fixture
def cliente(db: Session):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def registrado(cliente: TestClient):
    """Factory: registrado(**overrides) -> (headers, cliente_id, cuenta_id).
    Permite registrar un segundo cliente distinto para pruebas de aislamiento."""
    def _crear(**overrides):
        r = cliente.post("/auth/registro", json={**MARIA, **overrides})
        assert r.status_code == 201, r.text
        body = r.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["cliente_id"], body["cuenta_id"]
    return _crear


@pytest.fixture
def token_analista(db: Session):
    """No hay endpoint para crear un analista; se inserta directo y se firma el token a mano."""
    usuario = Usuario(email="analista@bancocloud.pe", password_hash=hash_password("Analista1234"), rol="analista")
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    token = crear_token(usuario.usuario_id, "analista", None)
    return {"Authorization": f"Bearer {token}"}
