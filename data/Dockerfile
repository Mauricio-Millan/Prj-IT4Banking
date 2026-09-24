# Imagen del pipeline de datos BancoCloud (Prefect + SQL Server). Corre como Container Apps
# Job (Scheduled, cron '0 1 * * *'): arranca, ejecuta el flujo una vez, termina. Mismo driver
# ODBC que backend/Dockerfile (msodbcsql18) porque habla con el mismo motor T-SQL (OLTP y DW).
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg2 \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/ms.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ms.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flows ./flows
COPY sql ./sql

RUN useradd -r appuser && chown -R appuser /app
USER appuser

ENTRYPOINT ["python", "-m", "flows.carga_diaria"]
