from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_cliente
from app.schemas.cuentas import ComisionRetiroOut, CuentaOut, SaldoOut
from app.schemas.transacciones import MovimientoOut, MovimientosPagina
from app.services import comisiones as comisiones_service
from app.services import cuentas as cuentas_service
from app.services.transacciones import retiros_este_mes

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


@router.get("", response_model=list[CuentaOut])
def listar(db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    return cuentas_service.listar(db, cliente_id)


@router.get("/{cuenta_id}/saldo", response_model=SaldoOut)
def saldo(cuenta_id: int, db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    cuenta = cuentas_service.obtener_propia(db, cliente_id, cuenta_id)
    return SaldoOut(cuenta_id=cuenta.cuenta_id, numero_cuenta=cuenta.numero_cuenta, moneda=cuenta.moneda, saldo=cuenta.saldo)


@router.get("/{cuenta_id}/comision-retiro", response_model=ComisionRetiroOut)
def comision_retiro(cuenta_id: int, db: Session = Depends(get_db), cliente_id: int = Depends(require_cliente)):
    """HU-Tarifario-Comisiones V6: el frontend consulta esto antes de confirmar un retiro,
    con la misma fuente (calcular) que usara el backend al aplicarlo de verdad."""
    cuenta = cuentas_service.obtener_propia(db, cliente_id, cuenta_id)
    hoy = datetime.now(timezone.utc).date()
    tarifa, monto = comisiones_service.calcular(db, "retiro", cuenta.cuenta_id, hoy)
    restantes = None
    if tarifa is not None and tarifa.gratis_por_mes is not None:
        usados = retiros_este_mes(db, cuenta.cuenta_id, hoy)
        restantes = max(tarifa.gratis_por_mes - usados, 0)
    return ComisionRetiroOut(monto=monto, retiros_gratis_restantes=restantes)


@router.get("/{cuenta_id}/movimientos", response_model=MovimientosPagina)
def movimientos(
    cuenta_id: int,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    cliente_id: int = Depends(require_cliente),
):
    filas, total, numeros = cuentas_service.movimientos(db, cliente_id, cuenta_id, desde, hasta, pagina, tamano)
    items = [
        MovimientoOut(
            transaccion_id=t.transaccion_id, fecha_hora=t.fecha_hora, tipo=t.tipo, monto=t.monto,
            canal=t.canal, estado=t.estado, concepto=t.concepto, direccion=direccion,
            cuenta_origen_id=t.cuenta_origen_id, cuenta_destino_id=t.cuenta_destino_id,
            cuenta_origen_numero=numeros.get(t.cuenta_origen_id), cuenta_destino_numero=numeros.get(t.cuenta_destino_id),
        )
        for t, direccion in filas
    ]
    return MovimientosPagina(items=items, total=total, pagina=pagina, tamano=tamano)
