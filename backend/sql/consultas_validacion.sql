-- Consultas de validacion del libro mayor (HU-Libro-Mayor-Partida-Doble).
-- No son parte de la app en tiempo de ejecucion: uso manual/auditoria para confirmar
-- que el saldo materializado (cuenta.saldo, el subledger) siempre es reconstruible
-- desde el libro mayor de partida doble (asiento_contable / movimiento_contable).

-- 1) Reconciliacion por cuenta: SUM(HABER) - SUM(DEBE) debe ser exactamente igual a cuenta.saldo.
--    Una fila con diferencia <> 0 es una alerta real (ver Arquitectura-Core-Banking-Tecnica.md §1.1:
--    "Divergencia > 0 dispara alerta, nunca se ajusta en silencio"), nunca deberia aparecer si
--    services/transacciones.py::crear() es la unica via de mutacion de saldo.
SELECT
    c.cuenta_id,
    c.saldo AS saldo_materializado,
    COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0) AS saldo_reconciliado,
    c.saldo - COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0) AS diferencia
FROM cuenta c
LEFT JOIN movimiento_contable mc ON mc.cuenta_cliente_id = c.cuenta_id
GROUP BY c.cuenta_id, c.saldo
HAVING c.saldo <> COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0);
-- Sin filas = todo reconciliado. Quitar el HAVING para ver la reconciliacion completa, no solo las alertas.

-- 2) Todo asiento debe balancear (defensa en profundidad ya reforzada por trg_asiento_balanceado;
--    esta consulta es para auditoria manual, no deberia devolver filas nunca).
SELECT
    asiento_id,
    SUM(CASE WHEN tipo_movimiento = 'D' THEN importe ELSE 0 END) AS suma_debe,
    SUM(CASE WHEN tipo_movimiento = 'H' THEN importe ELSE 0 END) AS suma_haber
FROM movimiento_contable
GROUP BY asiento_id
HAVING SUM(CASE WHEN tipo_movimiento = 'D' THEN importe ELSE 0 END)
     <> SUM(CASE WHEN tipo_movimiento = 'H' THEN importe ELSE 0 END);

-- 3) Toda transaccion aplicada debe tener exactamente un asiento original (no huerfanas, no duplicadas).
--    El indice unico filtrado ux_asiento_transaccion_original ya impide el duplicado; esta consulta
--    detecta el caso de una transaccion SIN asiento (bug de integracion, nunca deberia ocurrir).
SELECT t.transaccion_id, t.tipo, t.monto
FROM transaccion t
LEFT JOIN asiento_contable ac ON ac.transaccion_id = t.transaccion_id AND ac.tipo_operacion <> 'reversion'
WHERE t.estado = 'aplicada' AND ac.asiento_id IS NULL;
