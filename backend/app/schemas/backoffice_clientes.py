from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.cuentas import CuentaOut


class ClienteConCuentasOut(BaseModel):
    """Excepcion explicita a V14 (HU-Gestion-Usuarios-Internos-Backoffice: 'sin listado libre
    de clientes'), acotada a rol admin: el admin es quien ya gestiona es_empleado y usuarios
    internos, y necesita ubicar cliente_id sin depender de que exista un caso (prestamo/queja)
    abierto. analista sigue sin acceso a esta ruta."""
    model_config = ConfigDict(from_attributes=True)

    cliente_id: int
    codigo_cliente: str
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str
    email: str
    telefono: str | None
    region: str
    segmento: str
    estado: str
    es_empleado: bool
    fecha_alta: date
    cuentas: list[CuentaOut]


class ClientesPagina(BaseModel):
    items: list[ClienteConCuentasOut]
    total: int
    pagina: int
    tamano: int
