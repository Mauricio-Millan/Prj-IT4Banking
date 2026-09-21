"""Valida que el modelo compila y que los CHECK de negocio bloquean datos invalidos.
Corre sobre SQLite en memoria: no necesita Azure."""
import os
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, Cliente, Cuenta, Prestamo, Transaccion
from app.models.prestamo import bucket_de


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Cliente(cliente_id=1, codigo_cliente="1234567895", tipo_documento="DNI", numero_documento="12345678",
                      nombres="Maria", apellidos="Quispe", fecha_nacimiento=date(1998, 5, 1),
                      email="maria@test.pe", region="Lima"))
        s.commit()
        yield s


def test_crea_todas_las_tablas():
    assert {"cliente", "usuario", "cuenta", "tarjeta", "prestamo", "transaccion",
            "queja", "resumen_ejecutivo", "genai_log", "audit_log"} <= set(Base.metadata.tables)


def test_saldo_negativo_rechazado(db):
    db.add(Cuenta(cliente_id=1, numero_cuenta="00110000000019", cci="09900100110000000019" + "00", saldo=-1))
    with pytest.raises(IntegrityError):
        db.commit()


def test_monto_cero_rechazado(db):
    db.add(Transaccion(tipo="deposito", monto=0, canal="web"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_bucket_invalido_rechazado(db):
    db.add(Prestamo(cliente_id=1, monto_original=1000, saldo_capital=1000, tasa=25, plazo=12, bucket_mora="99"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_bucket_de():
    assert [bucket_de(d) for d in (0, 1, 30, 31, 60, 61, 90, 91)] == \
           ["0", "1-30", "1-30", "31-60", "31-60", "61-90", "61-90", ">90"]
