-- Esquema gold (HU-Analitica-DW-PowerBI): estrella Kimball construida desde silver.*.
-- Corre una vez contra bancocloud_dw (local) / bancocloud-dw-<env> (Azure), despues de
-- ddl_silver.sql. Idempotente: los IF de abajo permiten reejecutar sin duplicar nada.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'gold') EXEC('CREATE SCHEMA gold');
GO

-- ── Dimensiones estaticas (no dependen de silver, se siembran una sola vez aqui) ──────────

IF OBJECT_ID('gold.dim_producto') IS NULL
CREATE TABLE gold.dim_producto (
    producto_id INT PRIMARY KEY,
    tipo VARCHAR(20) NOT NULL,
    nombre VARCHAR(60) NOT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM gold.dim_producto)
INSERT INTO gold.dim_producto (producto_id, tipo, nombre) VALUES
    (1, 'cuenta_ahorro', 'Cuenta de ahorro'),
    (2, 'cuenta_corriente', 'Cuenta corriente'),
    (3, 'tarjeta_debito', 'Tarjeta de débito'),
    (4, 'prestamo', 'Préstamo de consumo');
GO

-- Mismo dominio que config.CANALES (data/flows/config.py) -- duplicado deliberado, ver nota ahi.
IF OBJECT_ID('gold.dim_canal') IS NULL
CREATE TABLE gold.dim_canal (
    canal_id INT PRIMARY KEY,
    canal VARCHAR(10) NOT NULL UNIQUE
);
GO
IF NOT EXISTS (SELECT 1 FROM gold.dim_canal)
INSERT INTO gold.dim_canal (canal_id, canal) VALUES
    (1, 'web'), (2, 'app'), (3, 'cajero'), (4, 'agente'), (5, 'sistema');
GO

-- Mismo dominio que config.REGIONES -- duplicado deliberado, ver nota ahi.
IF OBJECT_ID('gold.dim_region') IS NULL
CREATE TABLE gold.dim_region (
    region_id INT IDENTITY PRIMARY KEY,
    region VARCHAR(50) NOT NULL UNIQUE
);
GO
IF NOT EXISTS (SELECT 1 FROM gold.dim_region)
INSERT INTO gold.dim_region (region) VALUES
    ('Amazonas'), ('Áncash'), ('Apurímac'), ('Arequipa'), ('Ayacucho'), ('Cajamarca'), ('Callao'),
    ('Cusco'), ('Huancavelica'), ('Huánuco'), ('Ica'), ('Junín'), ('La Libertad'), ('Lambayeque'),
    ('Lima'), ('Loreto'), ('Madre de Dios'), ('Moquegua'), ('Pasco'), ('Piura'), ('Puno'),
    ('San Martín'), ('Tacna'), ('Tumbes'), ('Ucayali');
GO

-- Grano: un dia. Rango fijo 2024-2030 (V. diseño de la HU); no depende de silver.
IF OBJECT_ID('gold.dim_tiempo') IS NULL
CREATE TABLE gold.dim_tiempo (
    fecha DATE PRIMARY KEY,
    anio INT NOT NULL,
    mes INT NOT NULL,
    dia INT NOT NULL,
    trimestre INT NOT NULL,
    nombre_mes VARCHAR(20) NOT NULL,
    anio_mes CHAR(7) NOT NULL,          -- 'YYYY-MM', clave de hecho_rentabilidad_mensual
    es_fin_de_mes BIT NOT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM gold.dim_tiempo)
BEGIN
    ;WITH dias AS (
        SELECT CAST('2024-01-01' AS DATE) AS fecha
        UNION ALL
        SELECT DATEADD(DAY, 1, fecha) FROM dias WHERE fecha < '2030-12-31'
    )
    INSERT INTO gold.dim_tiempo (fecha, anio, mes, dia, trimestre, nombre_mes, anio_mes, es_fin_de_mes)
    SELECT
        fecha, YEAR(fecha), MONTH(fecha), DAY(fecha), DATEPART(QUARTER, fecha),
        DATENAME(MONTH, fecha), FORMAT(fecha, 'yyyy-MM'),
        CASE WHEN DAY(fecha) = DAY(EOMONTH(fecha)) THEN 1 ELSE 0 END
    FROM dias
    OPTION (MAXRECURSION 3000);
END
GO

-- ── Dimensión que sí cambia (se recarga en cada corrida desde silver.cliente) ─────────────

IF OBJECT_ID('gold.dim_cliente') IS NULL
CREATE TABLE gold.dim_cliente (
    cliente_id INT PRIMARY KEY,
    codigo_cliente VARCHAR(10) NOT NULL,
    es_empresa BIT NOT NULL,
    segmento VARCHAR(20) NOT NULL,
    region VARCHAR(50) NOT NULL,
    fecha_alta DATE NOT NULL,
    estado VARCHAR(20) NOT NULL
);
GO

-- ── Hechos ─────────────────────────────────────────────────────────────────────────────

-- Grano: una transaccion (solo estado='aplicada', V3). cliente_id: dueño de cuenta_origen,
-- o de cuenta_destino si no hay origen (deposito).
IF OBJECT_ID('gold.hecho_transaccion') IS NULL
CREATE TABLE gold.hecho_transaccion (
    transaccion_id INT PRIMARY KEY,
    fecha DATE NOT NULL,
    cliente_id INT NULL,
    cuenta_origen_id INT NULL,
    cuenta_destino_id INT NULL,
    canal_id INT NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    monto DECIMAL(18, 2) NOT NULL,
    concepto VARCHAR(80) NULL
);
GO

-- Grano: un prestamo por dia. dias_mora/bucket_mora/saldo_capital son copia exacta de
-- silver.prestamo (V4) -- esta HU no recalcula mora, la organiza en el grano de hecho.
IF OBJECT_ID('gold.hecho_cartera_diaria') IS NULL
CREATE TABLE gold.hecho_cartera_diaria (
    prestamo_id INT NOT NULL,
    fecha DATE NOT NULL,
    cliente_id INT NOT NULL,
    producto_id INT NOT NULL,
    saldo_capital DECIMAL(18, 2) NOT NULL,
    dias_mora INT NOT NULL,
    bucket_mora VARCHAR(5) NOT NULL,
    cuotas_pagadas INT NOT NULL,
    cuotas_vencidas INT NOT NULL,
    PRIMARY KEY (prestamo_id, fecha)
);
GO

-- Grano: producto x segmento x mes. ingresos/costo vienen exclusivamente del libro mayor
-- (silver.movimiento_contable, cuentas 4101/4201 de ingreso y 5101/5201 de gasto -- V5).
-- 5101/5201 aun no existen en el OLTP (HU-Gastos-Operativos-Intereses-Pasivos, pendiente):
-- costo sale en 0 hasta que esa HU se implemente, nunca estimado a mano.
IF OBJECT_ID('gold.hecho_rentabilidad_mensual') IS NULL
CREATE TABLE gold.hecho_rentabilidad_mensual (
    producto_id INT NOT NULL,
    segmento VARCHAR(20) NOT NULL,
    anio_mes CHAR(7) NOT NULL,
    ingresos DECIMAL(18, 2) NOT NULL,
    costo DECIMAL(18, 2) NOT NULL,
    margen DECIMAL(18, 2) NOT NULL,
    PRIMARY KEY (producto_id, segmento, anio_mes)
);
GO
