-- Soporte para el pipeline ADF pl_carga_silver (data/adf/). Prefect NO usa esto -- su silver.py
-- hace el enmascarado de cliente en Python antes del MERGE. Este stored procedure es el
-- equivalente en T-SQL, para que ADF pueda cargar silver.cliente sin reimplementar la logica
-- en un contenedor aparte. Corre UNA vez contra bancocloud-dw-<env>.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg') EXEC('CREATE SCHEMA stg');
GO

-- Landing transitorio de la particion Bronze de cliente, tal cual la escribe extraer_clientes().
-- ADF trunca y vuelve a llenar esta tabla en cada corrida (no es idempotente por si misma,
-- silver.sp_cargar_cliente es lo que hace el MERGE idempotente hacia silver.cliente).
IF OBJECT_ID('stg.cliente_bronze') IS NULL
CREATE TABLE stg.cliente_bronze (
    cliente_id INT NOT NULL,
    codigo_cliente VARCHAR(10) NOT NULL,
    tipo_documento VARCHAR(10) NOT NULL,
    numero_documento VARCHAR(20) NOT NULL,
    razon_social VARCHAR(150) NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL,
    segmento VARCHAR(20) NOT NULL,
    fecha_alta DATE NOT NULL,
    estado VARCHAR(20) NOT NULL
);
GO

-- Equivalente T-SQL de silver.enmascarar_clientes() (data/flows/silver.py):
--   - iniciales: siempre se calcula, nombre+apellido -> "N. A." (orden preservado via STRING_SPLIT
--     con ordinal, soportado en Azure SQL Database).
--   - documento_hash: SHA-256 de (sal + numero_documento), solo si NO es RUC. HASHBYTES + CONVERT
--     estilo 2 da hex en minuscula sin "0x", igual al hashlib.sha256(...).hexdigest() de Python.
--   - ruc/razon_social: solo si tipo_documento = 'RUC' (persona juridica, dato publico de SUNAT).
-- @sal_documento tiene el mismo default que config.SAL_DOCUMENTO en data/flows/config.py --
-- si ese valor cambia en el .env de Prefect, hay que pasarlo explicito aqui tambien o los hashes
-- de un mismo cliente no van a coincidir entre ambos pipelines.
CREATE OR ALTER PROCEDURE silver.sp_cargar_cliente
    @sal_documento VARCHAR(100) = 'cambiar-en-produccion'
AS
BEGIN
    SET NOCOUNT ON;

    MERGE silver.cliente AS tgt
    USING (
        SELECT
            b.cliente_id,
            b.codigo_cliente,
            (
                SELECT STRING_AGG(UPPER(LEFT(value, 1)) + '.', ' ') WITHIN GROUP (ORDER BY ordinal)
                FROM STRING_SPLIT(CONCAT(b.nombres, ' ', b.apellidos), ' ', 1)
                WHERE LEN(TRIM(value)) > 0
            ) AS iniciales,
            CASE WHEN b.tipo_documento = 'RUC' THEN NULL
                 ELSE LOWER(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CONCAT(@sal_documento, b.numero_documento)), 2))
            END AS documento_hash,
            CASE WHEN b.tipo_documento = 'RUC' THEN b.numero_documento ELSE NULL END AS ruc,
            CASE WHEN b.tipo_documento = 'RUC' THEN b.razon_social ELSE NULL END AS razon_social,
            b.segmento,
            b.region,
            b.fecha_alta,
            b.estado
        FROM stg.cliente_bronze b
    ) AS src
    ON tgt.cliente_id = src.cliente_id
    WHEN MATCHED THEN UPDATE SET
        codigo_cliente = src.codigo_cliente,
        iniciales = src.iniciales,
        documento_hash = src.documento_hash,
        ruc = src.ruc,
        razon_social = src.razon_social,
        segmento = src.segmento,
        region = src.region,
        fecha_alta = src.fecha_alta,
        estado = src.estado
    WHEN NOT MATCHED THEN INSERT (
        cliente_id, codigo_cliente, iniciales, documento_hash, ruc, razon_social, segmento, region, fecha_alta, estado
    ) VALUES (
        src.cliente_id, src.codigo_cliente, src.iniciales, src.documento_hash, src.ruc, src.razon_social, src.segmento, src.region, src.fecha_alta, src.estado
    );
END
GO
