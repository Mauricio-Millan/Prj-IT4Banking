from datetime import date

from app.core.tarjetas_crypto import cifrar_pan, huella_pan
from app.models import Tarjeta


def _tarjeta_dummy(cuenta_id: int, ultimos_4: str) -> Tarjeta:
    pan = f"549900991234{ultimos_4}"  # 16 digitos, DV no verificado aqui: no es el foco de este test
    return Tarjeta(cuenta_id=cuenta_id, tipo_tarjeta="credito", ultimos_4=ultimos_4,
                   pan_cifrado=cifrar_pan(pan, cuenta_id), pan_hmac=huella_pan(pan),
                   fecha_emision=date(2024, 1, 1), fecha_vencimiento=date(2028, 1, 1))


def test_lista_solo_tarjetas_propias(cliente, registrado, db):
    # cada registrado() ya emite su propia tarjeta de debito (ver test_auth.py); se agrega
    # una segunda tarjeta a mano para probar aislamiento con mas de una tarjeta por cliente.
    headers_a, _, cuenta_a = registrado()
    _, _, cuenta_b = registrado(numero_documento="70011223", email="otra@correo.pe")

    db.add(_tarjeta_dummy(cuenta_a, "1234"))
    db.add(_tarjeta_dummy(cuenta_b, "9999"))
    db.commit()

    r = cliente.get("/tarjetas", headers=headers_a)
    assert r.status_code == 200
    ultimos4 = {t["ultimos_4"] for t in r.json()}
    assert "9999" not in ultimos4  # es de cuenta_b, no debe verse
    assert "1234" in ultimos4 and len(ultimos4) == 2  # la del onboarding + la sembrada a mano
