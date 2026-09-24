"""Flujo Prefect: OLTP -> Bronze (ADLS/disco) -> validacion (RNF-05) -> Silver (Azure SQL DW).
Corre despues de app/jobs/cierre_diario.py (backend) para la misma fecha (V7): asi lee
dias_mora/bucket_mora/segmento ya actualizados del dia, nunca los del dia anterior.

Uso local: python -m flows.carga_diaria [--fecha AAAA-MM-DD]
--fecha: backfill de un dia concreto; por defecto ayer (asi la corrida de la madrugada
procesa el dia que acaba de cerrar). En el Container Apps Job, la variable de entorno FECHA
cumple el mismo rol (ver Docs/ci-cd-estrategia.md).
"""
import argparse
import hashlib
import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from prefect import flow, task
from sqlalchemy import create_engine, text

from . import calidad, config, extraer, silver


@task(retries=3, retry_delay_seconds=60)
def extraer_datos(fecha: date) -> dict[str, pd.DataFrame]:
    return extraer.extraer_todo(fecha)


@task
def escribir_bronze(crudo: dict[str, pd.DataFrame], fecha: date) -> None:
    """Inmutable: una re-ejecucion de la misma fecha sobrescribe la particion completa (V1).
    ponytail: solo filesystem local/montado por ahora (Path). BRONZE_PATH="abfs://..." (ADLS)
    funcionaria con df.to_parquet via fsspec/adlfs sin cambiar esta funcion, pero el hash
    sha256 y el manifest asumen Path -- cablear eso es el paso pendiente cuando exista el
    storage account real (ver runbook en Docs/ci-cd-estrategia.md)."""
    base = Path(config.BRONZE_PATH)
    manifest = {
        "fecha": fecha.isoformat(), "version_imagen": config.VERSION_IMAGEN,
        "timestamp": datetime.utcnow().isoformat(), "tablas": {},
    }
    for tabla, df in crudo.items():
        carpeta = base / tabla / f"fecha={fecha.isoformat()}"
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / "part-0.parquet"
        df.to_parquet(archivo, index=False)
        manifest["tablas"][tabla] = {"filas": len(df), "sha256": hashlib.sha256(archivo.read_bytes()).hexdigest()}

    manifest_dir = base / "_manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / f"fecha={fecha.isoformat()}.json").write_text(json.dumps(manifest, indent=2, default=str))


@task
def validar_datos(crudo: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    return calidad.validar(crudo)


@task
def registrar_rechazos(rechazos: pd.DataFrame, corrida_id: str, fecha: date) -> None:
    if rechazos.empty:
        return
    filas = rechazos.copy()
    filas["corrida_id"] = corrida_id
    filas["fecha"] = fecha
    filas.to_sql("rechazos", create_engine(config.dw_url()), schema="dq", if_exists="append", index=False)


@task
def cargar_silver_task(validas: dict[str, pd.DataFrame]) -> None:
    silver.cargar_silver(validas)


def _iniciar_corrida(fecha: date) -> str:
    corrida_id = str(uuid.uuid4())
    with create_engine(config.dw_url()).begin() as conn:
        conn.execute(text(
            "INSERT INTO ops.pipeline_runs (corrida_id, fecha_datos, inicio, estado, version_imagen, prefect_run_id) "
            "VALUES (:id, :fecha, :inicio, 'en_curso', :version, :run_id)"
        ), {
            "id": corrida_id, "fecha": fecha, "inicio": datetime.utcnow(),
            "version": config.VERSION_IMAGEN, "run_id": os.environ.get("PREFECT_RUN_ID", ""),
        })
    return corrida_id


def _cerrar_corrida(corrida_id: str, leidas: int, rechazadas: int, estado: str, mensaje_error: str | None = None) -> None:
    with create_engine(config.dw_url()).begin() as conn:
        conn.execute(text(
            "UPDATE ops.pipeline_runs SET fin=:fin, estado=:estado, filas_leidas=:leidas, "
            "filas_rechazadas=:rechazadas, mensaje_error=:mensaje WHERE corrida_id=:id"
        ), {
            "fin": datetime.utcnow(), "estado": estado, "leidas": leidas,
            "rechazadas": rechazadas, "mensaje": (mensaje_error or "")[:500], "id": corrida_id,
        })


@flow(name="carga_diaria", retries=0)
def carga_diaria(fecha: date | None = None) -> None:
    fecha = fecha or (date.today() - timedelta(days=1))
    corrida_id = _iniciar_corrida(fecha)
    try:
        crudo = extraer_datos(fecha)
        escribir_bronze(crudo, fecha)
        validas, rechazadas = validar_datos(crudo)
        registrar_rechazos(rechazadas, corrida_id, fecha)
        cargar_silver_task(validas)

        advertencia = calidad.advertencia_volumen(crudo["transaccion"])
        if advertencia:
            print(f"ADVERTENCIA: {advertencia}")

        leidas = sum(len(df) for df in crudo.values())
        _cerrar_corrida(corrida_id, leidas, len(rechazadas), "ok")
        print(f"carga_diaria {fecha.isoformat()}: ok, {leidas} leidas, {len(rechazadas)} rechazadas")
    except Exception as e:
        _cerrar_corrida(corrida_id, 0, 0, "error", mensaje_error=str(e))
        raise  # V4: el proceso debe terminar con codigo != 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fecha", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    carga_diaria(args.fecha)
