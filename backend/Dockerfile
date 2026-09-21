# Imagen del backend BancoCloud (FastAPI + SQL Server).
# Corre "alembic upgrade head" al arrancar para no depender de un job aparte.
# ponytail: con min-replicas>1 dos réplicas podrían migrar a la vez; aceptable
# para la demo (min-replicas=0/1). Si escala, mover la migración a un paso previo.
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

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN useradd -r appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
