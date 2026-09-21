"""Uso puntual para habilitar el login de backoffice en la demo manual. No es un seed permanente."""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Usuario

EMAIL = "analista.demo@bancocloud.pe"
PASSWORD = "Analista2026!"

db = SessionLocal()
existente = db.scalar(select(Usuario).where(Usuario.email == EMAIL))
if existente:
    print("ya existe:", EMAIL)
else:
    db.add(Usuario(email=EMAIL, password_hash=hash_password(PASSWORD), rol="analista"))
    db.commit()
    print("creado:", EMAIL, "/", PASSWORD)
