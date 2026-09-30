"""MERGE generico por clave natural (idempotente) via tabla de staging -- usado tanto por
silver.py (silver.*) como por analitica.py (gold.*). Extraido de silver.py::_merge para no
duplicar la misma logica de staging+MERGE en dos esquemas."""
import pandas as pd
from sqlalchemy import Engine, text


def merge(engine: Engine, df: pd.DataFrame, esquema: str, tabla: str, clave: str | list[str], columnas: list[str]) -> None:
    """clave: columna(s) de la clave natural -- lista para hechos con grano compuesto
    (ej. hecho_cartera_diaria: prestamo_id + fecha)."""
    if df.empty:
        return
    claves = [clave] if isinstance(clave, str) else clave
    staging = f"stg_{tabla}"
    df[columnas].to_sql(staging, engine, schema=esquema, if_exists="replace", index=False)
    on_clause = " AND ".join(f"tgt.{c} = src.{c}" for c in claves)
    set_clause = ", ".join(f"tgt.{c} = src.{c}" for c in columnas if c not in claves)
    insert_cols = ", ".join(columnas)
    insert_vals = ", ".join(f"src.{c}" for c in columnas)
    merge_sql = f"""
        MERGE {esquema}.{tabla} AS tgt
        USING {esquema}.{staging} AS src ON {on_clause}
        WHEN MATCHED THEN UPDATE SET {set_clause}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});
    """
    with engine.begin() as conn:
        conn.execute(text(merge_sql))
        conn.execute(text(f"DROP TABLE {esquema}.{staging}"))
