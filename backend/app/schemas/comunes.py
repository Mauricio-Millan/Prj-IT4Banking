from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Todo campo de dinero sale por la API como string exacto ("1234.50"), nunca como
# float/JSON number — evita cualquier ambigüedad de redondeo en el viaje de ida.
# Para campos de ENTRADA basta con Decimal = Field(gt=0, max_digits=18, decimal_places=2);
# Pydantic v2 ya rechaza más de 2 decimales sin necesidad de un validador propio.
Dinero = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str)]
