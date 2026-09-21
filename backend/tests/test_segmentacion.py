from datetime import date, timedelta
from decimal import Decimal

from app.models import Cliente, Cuenta
from app.services.segmentacion import calcular_nuevo_segmento, reevaluar_segmento

HOY = date(2026, 9, 21)


def _fecha_nacimiento(edad: int) -> date:
    return HOY.replace(year=HOY.year - edad)


def test_ascenso_automatico_a_premium_por_saldo():
    nuevo, dias = calcular_nuevo_segmento("clasico", 0, Decimal("25000.00"), _fecha_nacimiento(40), HOY)
    assert (nuevo, dias) == ("premium", 0)


def test_no_desciende_por_un_dia_bajo_el_umbral():
    nuevo, dias = calcular_nuevo_segmento("premium", 0, Decimal("15000.00"), _fecha_nacimiento(40), HOY)
    assert (nuevo, dias) == ("premium", 1)


def test_desciende_tras_30_dias_consecutivos_bajo_el_umbral():
    nuevo, dias = calcular_nuevo_segmento("premium", 29, Decimal("15000.00"), _fecha_nacimiento(40), HOY)
    assert (nuevo, dias) == ("clasico", 0)


def test_recupera_premium_antes_de_los_30_dias():
    nuevo, dias = calcular_nuevo_segmento("premium", 10, Decimal("25000.00"), _fecha_nacimiento(40), HOY)
    assert (nuevo, dias) == ("premium", 0)


def test_joven_pasa_a_clasico_al_cumplir_30_sin_ser_premium():
    nuevo, dias = calcular_nuevo_segmento("joven", 0, Decimal("500.00"), _fecha_nacimiento(30), HOY)
    assert (nuevo, dias) == ("clasico", 0)


def test_clasico_nunca_vuelve_a_joven():
    # la edad nunca decrece: un clasico (siempre >=30 para haber llegado a serlo) se queda
    # clasico; la regla V10 es una garantia del algoritmo por edad, no un estado a rastrear aparte.
    nuevo, dias = calcular_nuevo_segmento("clasico", 0, Decimal("0.00"), _fecha_nacimiento(35), HOY)
    assert (nuevo, dias) == ("clasico", 0)


def test_reevaluar_segmento_nunca_toca_una_empresa(db):
    cliente = Cliente(codigo_cliente="1234567895", tipo_documento="RUC", numero_documento="20100070970",
                       razon_social="Empresa SAC", nombres="Rep", apellidos="Legal",
                       fecha_nacimiento=date(2000, 1, 1), email="empresa@correo.pe", region="Lima",
                       segmento="empresa", dias_bajo_umbral_premium=0)
    db.add(cliente)
    db.commit()

    reevaluar_segmento(db, cliente, HOY)
    assert cliente.segmento == "empresa"


def test_reevaluar_segmento_deja_rastro_en_audit_log(cliente, registrado, db):
    from app.models import AuditLog

    _, cliente_id, cuenta_id = registrado()
    db.query(Cuenta).filter_by(cuenta_id=cuenta_id).update({"saldo": Decimal("25000.00")})
    db.commit()

    cliente_obj = db.get(Cliente, cliente_id)
    reevaluar_segmento(db, cliente_obj, HOY)
    db.commit()

    assert cliente_obj.segmento == "premium"
    assert db.query(AuditLog).filter_by(accion="cambio_segmento", entidad_id=str(cliente_id)).count() == 1
