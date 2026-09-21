"""Primer admin del sistema (problema del huevo y la gallina): todos los demas usuarios
internos se crean despues via POST /backoffice/usuarios. Reemplaza a crear_analista_demo.py.
Corre una sola vez por base de datos (idempotente: no hace nada si el correo ya existe)."""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Usuario

EMAIL = "admin@bancocloud.pe"
PASSWORD_TEMPORAL = "CambiarAlPrimerIngreso1!"

db = SessionLocal()
existente = db.scalar(select(Usuario).where(Usuario.email == EMAIL))
if existente:
    print("ya existe:", EMAIL)
else:
    db.add(Usuario(email=EMAIL, password_hash=hash_password(PASSWORD_TEMPORAL), rol="admin",
                    activo=True, debe_cambiar_password=True))
    db.commit()
    print("creado:", EMAIL, "/", PASSWORD_TEMPORAL, "(debe cambiarla en el primer acceso)")
