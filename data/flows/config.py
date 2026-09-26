"""Configuracion del pipeline via variables de entorno (mismo patron que backend/app/core/config.py,
pero data/ es una imagen Docker separada -> sin importar nada de backend/).

OLTP_URL/DW_URL se leen perezosamente (no al importar el modulo): calidad.py no toca ninguna
base de datos y sus tests unitarios (DataFrames fijos) no deben requerir esas variables."""
import os


def oltp_url() -> str:
    # mssql+pyodbc://user:pass@host:1433/bancocloud-<env>?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes
    return os.environ["OLTP_URL"]


def dw_url() -> str:
    # mismo formato, apuntando a bancocloud_dw (local) / bancocloud-dw-<env> (Azure)
    return os.environ["DW_URL"]

# Local: carpeta en disco. Azure: "abfs://bronze-<env>@<storage>.dfs.core.windows.net" (pandas usa
# fsspec/adlfs para resolver el esquema abfs:// automaticamente, sin codigo propio de subida).
BRONZE_PATH = os.environ.get("BRONZE_PATH", "./bronze")


def storage_options() -> dict:
    """Credenciales para fsspec/adlfs cuando BRONZE_PATH es abfs:// (vacio para filesystem local).
    Auth por account key (Container App secret), no Managed Identity -- el tenant academico la
    bloquea (ver Docs/ci-cd-estrategia.md #2)."""
    key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    return {"account_key": key} if key else {}

VERSION_IMAGEN = os.environ.get("VERSION_IMAGEN", "local")
# Sal para el hash del documento en silver.cliente (V2/V10). Debe ser la misma entre corridas
# para que un mismo documento produzca siempre el mismo hash (permite JOIN/dedup en analitica
# sin re-exponer el numero real) pero nunca se expone fuera de este proceso.
SAL_DOCUMENTO = os.environ.get("SAL_DOCUMENTO", "cambiar-en-produccion")

# Duplicado deliberado de app/schemas/auth.py::REGIONES y del CHECK ck_transaccion_canal del
# OLTP: data/ es una imagen separada, sin dependencia de backend/. Si cambia el dominio en el
# OLTP, actualizar aqui tambien (ver nota en HU-Pipeline-ETL-Bronze-Silver.md).
REGIONES = (
    "Amazonas", "Áncash", "Apurímac", "Arequipa", "Ayacucho", "Cajamarca", "Callao", "Cusco",
    "Huancavelica", "Huánuco", "Ica", "Junín", "La Libertad", "Lambayeque", "Lima", "Loreto",
    "Madre de Dios", "Moquegua", "Pasco", "Piura", "Puno", "San Martín", "Tacna", "Tumbes", "Ucayali",
)
CANALES = ("web", "app", "cajero", "agente", "sistema")
