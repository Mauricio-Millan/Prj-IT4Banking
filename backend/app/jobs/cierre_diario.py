"""Job diario: (1, HU-Ciclo-Vida-Prestamo) marca cuotas vencidas y recalcula dias_mora/
bucket_mora de los prestamos vigentes; (2, HU-Gastos-Operativos-Intereses-Pasivos) devenga el
interes pasivo de cada cuenta de ahorro activa, ANTES de segmentacion para que esta ya vea el
saldo acreditado; (3, HU-Segmentacion-Clientes) re-evalua joven/clasico/premium de cada cliente
que no sea 'empresa', usando el saldo ya actualizado del dia. Un solo Job, un solo cron: no hay
razon para procesos separados. Idempotente: correrlo dos veces el mismo dia no cambia nada la
segunda vez -- (1)/(3) porque los recalculos se derivan siempre del estado actual, y (2) porque
devengar_interes_pasivo se salta cualquier cuenta que ya tenga un asiento 'interes_pasivo' fechado
ese mismo dia (sin este chequeo, correr el Job dos veces duplicaria el interes del dia).

Uso: python -m app.jobs.cierre_diario [--fecha AAAA-MM-DD]
--fecha: para simular en local o en tests; por defecto hoy.

Pensado para correr como Container Apps Job (cron '30 0 * * *'), antes del pipeline de la
01:00 (HU-Pipeline-Diario-DW, aun no implementada). No se agrega aqui la definicion Bicep del
job: este proyecto no tiene ninguna infraestructura de Container Apps desplegada todavia
(no hay carpeta infra/ ni Bicep en el repo) — el proximo paso de esa pieza es de infra, no de
codigo de aplicacion.
"""
import argparse
from datetime import date

from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.models import AuditLog, Cliente, Cuenta, Cuota, Prestamo
from app.services.intereses_pasivos import devengar_interes_pasivo
from app.services.prestamos import recalcular_mora
from app.services.segmentacion import reevaluar_segmento


def ejecutar(fecha: date) -> None:
    db = SessionLocal()
    try:
        resultado = db.execute(
            update(Cuota).where(Cuota.estado == "pendiente", Cuota.fecha_vencimiento < fecha).values(estado="vencida")
        )
        cuotas_vencidas = resultado.rowcount

        prestamos_vigentes = list(db.scalars(select(Prestamo).where(Prestamo.estado == "vigente")))
        for prestamo in prestamos_vigentes:
            recalcular_mora(db, prestamo, fecha)

        # Antes de segmentacion: el ascenso a premium debe ver el saldo ya con el interes acreditado.
        cuentas_ahorro = list(db.scalars(select(Cuenta).where(Cuenta.tipo_cuenta == "ahorro", Cuenta.estado == "activa")))
        for cuenta in cuentas_ahorro:
            devengar_interes_pasivo(db, cuenta, fecha)

        clientes_reevaluables = list(db.scalars(select(Cliente).where(Cliente.segmento != "empresa")))
        for cliente in clientes_reevaluables:
            reevaluar_segmento(db, cliente, fecha)

        db.add(AuditLog(usuario_id=None, accion="cierre_diario", entidad="prestamo", entidad_id=fecha.isoformat()))
        db.commit()
        print(f"cierre_diario {fecha.isoformat()}: {cuotas_vencidas} cuota(s) marcadas vencidas, "
              f"{len(prestamos_vigentes)} prestamo(s) vigente(s) recalculados, "
              f"{len(cuentas_ahorro)} cuenta(s) de ahorro evaluadas para interes pasivo, "
              f"{len(clientes_reevaluables)} cliente(s) re-evaluados")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    ejecutar(args.fecha)
