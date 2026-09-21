from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "BancoCloud API"
    env: str = "dev"
    # mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes
    database_url: str
    jwt_secret: str = "cambiar-en-produccion"
    jwt_exp_minutes: int = 30
    # Backoffice (HU-Gestion-Usuarios-Internos-Backoffice): sesion corta para personal interno,
    # y dominio que distingue un correo de empleado de uno de cliente.
    jwt_exp_minutes_backoffice: int = 15
    dominio_corporativo: str = "bancocloud.pe"
    cors_origins: str = "http://localhost:4200"

    # Numeracion bancaria (ficticios: no usar el codigo real de ningun banco).
    # Interbank es 003, BCP 002, BBVA 011 — ninguno de esos aqui a proposito.
    oficina: str = "001"
    banco_codigo_cce: str = "099"

    # Custodia de tarjetas (HU-Tarjeta-Datos-Cifrados-Revelar). BIN ficticio, no ruteable
    # por ninguna red de pago real. Las dos claves son AES-256/HMAC-SHA256 de 32 bytes en
    # base64 y NO tienen default a proposito: sin ellas la API debe fallar en el arranque,
    # no en la primera peticion de revelado. Generar con:
    # python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
    tarjeta_bin: str = "54990099"
    tarjeta_clave_cifrado: str
    tarjeta_clave_hmac: str


settings = Settings()
