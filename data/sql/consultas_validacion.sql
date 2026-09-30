-- V6 (HU-Analitica-DW-PowerBI): conciliacion Gold vs. Silver.
--
-- silver.cuenta es un snapshot del saldo ACTUAL (no historizado -- una corrida sobrescribe la
-- fila anterior via MERGE), asi que no hay forma de leer "el saldo de ayer" para comparar
-- contra el movimiento de un dia puntual. La conciliacion que SI es verificable con lo que el
-- modelo guarda es de punta a punta: el saldo actual de una cuenta debe ser exactamente la
-- suma de todos los movimientos que le han pasado por gold.hecho_transaccion desde que existe
-- (deposito/transferencia entrante suman, retiro/transferencia saliente/comision/pago_prestamo
-- restan) -- siempre que gold tenga cargado el historico completo de esa cuenta, no solo el
-- ultimo dia. Ejecutar despues de una corrida de backfill completa (o desde el dia de apertura
-- de cada cuenta) para que la comparacion tenga sentido.
--
-- Filas con diferencia != 0 se listan para revision manual; esta consulta no corrige nada.

WITH movimiento_neto AS (
    SELECT
        cuenta_id,
        SUM(CASE WHEN entrada = 1 THEN monto ELSE -monto END) AS neto
    FROM (
        SELECT cuenta_destino_id AS cuenta_id, monto, 1 AS entrada FROM gold.hecho_transaccion WHERE cuenta_destino_id IS NOT NULL
        UNION ALL
        SELECT cuenta_origen_id AS cuenta_id, monto, 0 AS entrada FROM gold.hecho_transaccion WHERE cuenta_origen_id IS NOT NULL
    ) mov
    GROUP BY cuenta_id
)
SELECT
    c.cuenta_id,
    c.numero_cuenta,
    c.saldo AS saldo_silver,
    ISNULL(n.neto, 0) AS neto_hecho_transaccion,
    c.saldo - ISNULL(n.neto, 0) AS diferencia
FROM silver.cuenta c
LEFT JOIN movimiento_neto n ON n.cuenta_id = c.cuenta_id
WHERE ABS(c.saldo - ISNULL(n.neto, 0)) > 0.01
ORDER BY ABS(c.saldo - ISNULL(n.neto, 0)) DESC;
