-- Esquema silver (entregable de HU-Pipeline-ETL-Bronze-Silver) + dq/ops de soporte.
-- Corre UNA vez contra la base del DW (bancocloud_dw local / bancocloud-dw-<env> en Azure),
-- nunca contra el OLTP. Idempotente a nivel de "crear si no existe" via los IF de abajo.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'silver') EXEC('CREATE SCHEMA silver');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dq') EXEC('CREATE SCHEMA dq');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'ops') EXEC('CREATE SCHEMA ops');
GO

IF OBJECT_ID('silver.cliente') IS NULL
CREATE TABLE silver.cliente (
    cliente_id INT PRIMARY KEY,
    codigo_cliente VARCHAR(10) NOT NULL,
    iniciales VARCHAR(30) NULL,
    documento_hash CHAR(64) NULL,
    ruc VARCHAR(20) NULL,
    razon_social VARCHAR(150) NULL,
    segmento VARCHAR(20) NOT NULL,
    region VARCHAR(50) NOT NULL,
    fecha_alta DATE NOT NULL,
    estado VARCHAR(20) NOT NULL
);
GO

IF OBJECT_ID('silver.cuenta') IS NULL
CREATE TABLE silver.cuenta (
    cuenta_id INT PRIMARY KEY,
    cliente_id INT NOT NULL,
    numero_cuenta VARCHAR(14) NOT NULL,
    cci VARCHAR(20) NOT NULL,
    tipo_cuenta VARCHAR(20) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    saldo DECIMAL(18, 2) NOT NULL,
    fecha_apertura DATE NOT NULL,
    estado VARCHAR(20) NOT NULL
);
GO

IF OBJECT_ID('silver.prestamo') IS NULL
CREATE TABLE silver.prestamo (
    prestamo_id INT PRIMARY KEY,
    cliente_id INT NOT NULL,
    cuenta_desembolso_id INT NOT NULL,
    monto_original DECIMAL(18, 2) NOT NULL,
    saldo_capital DECIMAL(18, 2) NOT NULL,
    tasa DECIMAL(5, 2) NOT NULL,
    plazo INT NOT NULL,
    fecha_desembolso DATE NULL,
    dias_mora INT NOT NULL,
    bucket_mora VARCHAR(5) NOT NULL,
    estado VARCHAR(20) NOT NULL
);
GO

IF OBJECT_ID('silver.cuota') IS NULL
CREATE TABLE silver.cuota (
    cuota_id INT PRIMARY KEY,
    prestamo_id INT NOT NULL,
    numero INT NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    capital DECIMAL(18, 2) NOT NULL,
    interes DECIMAL(18, 2) NOT NULL,
    total DECIMAL(18, 2) NOT NULL,
    saldo_capital_despues DECIMAL(18, 2) NOT NULL,
    estado VARCHAR(10) NOT NULL,
    fecha_pago DATE NULL,
    transaccion_id INT NULL
);
GO

IF OBJECT_ID('silver.transaccion') IS NULL
CREATE TABLE silver.transaccion (
    transaccion_id INT PRIMARY KEY,
    cuenta_origen_id INT NULL,
    cuenta_destino_id INT NULL,
    fecha_hora DATETIME2 NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    monto DECIMAL(18, 2) NOT NULL,
    canal VARCHAR(10) NOT NULL,
    estado VARCHAR(20) NOT NULL,          -- V9: se conserva tal cual (aplicada/rechazada/reversada)
    concepto VARCHAR(80) NULL,
    transaccion_origen_id INT NULL
);
GO

IF OBJECT_ID('silver.movimiento_contable') IS NULL
CREATE TABLE silver.movimiento_contable (
    movimiento_id INT PRIMARY KEY,
    asiento_id INT NOT NULL,
    cuenta_contable_id INT NOT NULL,
    cuenta_cliente_id INT NULL,
    tipo_movimiento CHAR(1) NOT NULL,
    importe DECIMAL(19, 4) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    codigo_cuenta_contable VARCHAR(20) NOT NULL,
    fecha_contable DATE NOT NULL,
    tipo_operacion VARCHAR(30) NOT NULL,
    transaccion_id INT NULL
);
GO

IF OBJECT_ID('dq.rechazos') IS NULL
CREATE TABLE dq.rechazos (
    rechazo_id INT IDENTITY PRIMARY KEY,
    corrida_id VARCHAR(36) NOT NULL,
    tabla VARCHAR(30) NOT NULL,
    clave VARCHAR(50) NOT NULL,
    regla VARCHAR(50) NOT NULL,
    valor VARCHAR(200) NULL,
    fecha DATE NOT NULL
);
GO

IF OBJECT_ID('ops.pipeline_runs') IS NULL
CREATE TABLE ops.pipeline_runs (
    corrida_id VARCHAR(36) PRIMARY KEY,
    fecha_datos DATE NOT NULL,
    inicio DATETIME2 NOT NULL,
    fin DATETIME2 NULL,
    estado VARCHAR(20) NOT NULL,           -- en_curso | ok | error
    filas_leidas INT NULL,
    filas_rechazadas INT NULL,
    version_imagen VARCHAR(60) NULL,
    prefect_run_id VARCHAR(60) NULL,
    mensaje_error VARCHAR(500) NULL
);
GO
