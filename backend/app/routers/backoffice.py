from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.auditoria import auditar_consulta
from app.core.db import get_db
from app.core.security import UsuarioActual, require_role
from app.schemas.backoffice_clientes import ClienteConCuentasOut, ClientesPagina
from app.schemas.clientes_empresa import ClienteEmpresaIn, ClienteEmpresaOut, EmpresaListadaOut
from app.schemas.prestamos import DecisionPrestamoIn, PrestamoOut, PrestamoRevisionOut
from app.schemas.quejas import DecisionQuejaIn, MetricasQuejasOut, QuejaOut, QuejaRevisionOut
from app.schemas.usuarios_internos import ActualizarUsuarioInternoIn, EsEmpleadoIn, UsuarioInternoIn, UsuarioInternoOut
from app.services import clientes as clientes_service
from app.services import clientes_empresa as clientes_empresa_service
from app.services import prestamos as prestamos_service
from app.services import quejas as quejas_service
from app.services import usuarios_internos as usuarios_internos_service

# Separado de routers/prestamos.py a proposito: refleja la misma separacion que ya existe
# en el frontend (BackofficeLayout es un arbol de rutas aparte). Punto de crecimiento natural
# para /backoffice/quejas cuando se construya esa fase.
router = APIRouter(prefix="/backoffice", tags=["backoffice"])


@router.get("/prestamos", response_model=list[PrestamoRevisionOut])
def listar_prestamos(
    estado: str = "solicitado",
    codigo_cliente: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role("analista", "admin")),
    __=Depends(auditar_consulta("cola_prestamos")),
):
    try:
        return prestamos_service.listar_cartera(db, estado=estado, codigo_cliente=codigo_cliente)
    except prestamos_service.EstadoInvalido:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Estado de préstamo inválido")


@router.patch("/prestamos/{prestamo_id}", response_model=PrestamoOut)
def resolver(
    prestamo_id: int,
    datos: DecisionPrestamoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("analista", "admin")),
):
    try:
        p = prestamos_service.resolver(db, prestamo_id, datos.decision, usuario.usuario_id, usuario.rol,
                                        ip=request.client.host if request.client else None)
    except prestamos_service.PrestamoYaResuelto:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="La solicitud ya fue resuelta")
    except prestamos_service.RequiereAdmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Este caso involucra a un empleado: solo un admin puede resolverlo")
    return prestamos_service.a_schema(p)


@router.get("/clientes", response_model=ClientesPagina)
def listar_clientes(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
    __=Depends(auditar_consulta("listado_clientes")),
):
    filas, total = clientes_service.listar_con_cuentas(db, pagina, tamano)
    items = [ClienteConCuentasOut.model_validate(c) for c in filas]
    return ClientesPagina(items=items, total=total, pagina=pagina, tamano=tamano)


@router.post("/usuarios", response_model=UsuarioInternoOut, status_code=status.HTTP_201_CREATED)
def crear_usuario_interno(
    datos: UsuarioInternoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("admin")),
):
    try:
        return usuarios_internos_service.crear(db, datos, usuario.usuario_id,
                                                 ip=request.client.host if request.client else None)
    except usuarios_internos_service.EmailDuplicado:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo")


@router.get("/usuarios", response_model=list[UsuarioInternoOut])
def listar_usuarios_internos(
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
    __=Depends(auditar_consulta("usuarios_internos")),
):
    return usuarios_internos_service.listar(db)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioInternoOut)
def actualizar_usuario_interno(
    usuario_id: int,
    datos: ActualizarUsuarioInternoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("admin")),
):
    try:
        return usuarios_internos_service.actualizar(db, usuario_id, usuario.usuario_id, datos,
                                                      ip=request.client.host if request.client else None)
    except usuarios_internos_service.OperacionNoPermitida as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=e.mensaje)


@router.patch("/clientes/{cliente_id}/es-empleado", status_code=status.HTTP_204_NO_CONTENT)
def marcar_es_empleado(
    cliente_id: int,
    datos: EsEmpleadoIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("admin")),
):
    usuarios_internos_service.marcar_es_empleado(db, cliente_id, datos.es_empleado, usuario.usuario_id,
                                                  ip=request.client.host if request.client else None)


@router.post("/clientes-empresa", response_model=ClienteEmpresaOut, status_code=status.HTTP_201_CREATED)
def crear_cliente_empresa(
    datos: ClienteEmpresaIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("admin")),
):
    try:
        resultado = clientes_empresa_service.crear(db, datos, usuario.usuario_id,
                                                     ip=request.client.host if request.client else None)
    except clientes_empresa_service.RucDuplicado:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Ya existe una empresa con ese RUC")
    except clientes_empresa_service.EmailDuplicado:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo")

    cliente, cuenta, tarjeta = resultado["cliente"], resultado["cuenta"], resultado["tarjeta"]
    return ClienteEmpresaOut(
        cliente_id=cliente.cliente_id, codigo_cliente=cliente.codigo_cliente, ruc=cliente.numero_documento,
        razon_social=cliente.razon_social, cuenta_id=cuenta.cuenta_id, numero_cuenta=cuenta.numero_cuenta,
        cci=cuenta.cci, password_temporal=resultado["password_temporal"], tarjeta=tarjeta,
    )


@router.get("/clientes-empresa", response_model=list[EmpresaListadaOut])
def listar_clientes_empresa(
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
    __=Depends(auditar_consulta("clientes_empresa")),
):
    empresas = clientes_empresa_service.listar(db)
    return [
        EmpresaListadaOut(cliente_id=c.cliente_id, codigo_cliente=c.codigo_cliente, ruc=c.numero_documento,
                           razon_social=c.razon_social, region=c.region, fecha_alta=c.fecha_alta, estado=c.estado)
        for c in empresas
    ]


@router.get("/quejas", response_model=list[QuejaRevisionOut])
def listar_quejas(
    categoria: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role("analista", "admin")),
    __=Depends(auditar_consulta("cola_quejas")),
):
    """V11: cualquier analista/admin ve toda la cola; 'categoria' es un filtro de conveniencia,
    no una restriccion de acceso (sin RBAC por equipo en esta version — ver nota de alcance de la HU)."""
    return quejas_service.listar_cola(db, categoria)


@router.get("/quejas/metricas", response_model=MetricasQuejasOut)
def metricas_quejas(
    db: Session = Depends(get_db),
    _=Depends(require_role("analista", "admin")),
):
    # Registrado ANTES de /quejas/{queja_id} en el archivo: una ruta literal debe declararse
    # antes que una con parametro que tambien la matchearia (FastAPI resuelve por orden).
    return quejas_service.metricas(db)


@router.patch("/quejas/{queja_id}", response_model=QuejaOut)
def resolver_queja(
    queja_id: int,
    datos: DecisionQuejaIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(require_role("analista", "admin")),
):
    try:
        return quejas_service.revisar(db, queja_id, usuario.usuario_id, datos.categoria_final)
    except quejas_service.QuejaYaResuelta:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="La queja ya fue revisada")
