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

-- 4) HU-Ciclo-Vida-Prestamo V9: Sigma saldo_capital de prestamos vigentes debe ser igual al
--    saldo de la cuenta contable 1301 (Prestamos por cobrar): Sigma DEBE - Sigma HABER.
--    Una sola fila con la diferencia; debe ser 0.
SELECT
    (SELECT COALESCE(SUM(saldo_capital), 0) FROM prestamo WHERE estado = 'vigente') AS suma_saldo_capital_vigentes,
    (SELECT COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'D' THEN mc.importe ELSE -mc.importe END), 0)
     FROM movimiento_contable mc
     JOIN cuenta_contable cc ON cc.cuenta_contable_id = mc.cuenta_contable_id
     WHERE cc.codigo = '1301') AS saldo_1301,
    (SELECT COALESCE(SUM(saldo_capital), 0) FROM prestamo WHERE estado = 'vigente')
    - (SELECT COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'D' THEN mc.importe ELSE -mc.importe END), 0)
       FROM movimiento_contable mc
       JOIN cuenta_contable cc ON cc.cuenta_contable_id = mc.cuenta_contable_id
       WHERE cc.codigo = '1301') AS diferencia;

-- 5) HU-Ciclo-Vida-Prestamo V9: Sigma interes de cuotas pagadas debe ser igual al saldo de la
--    cuenta contable 4201 (Ingresos por intereses): Sigma HABER - Sigma DEBE.
SELECT
    (SELECT COALESCE(SUM(interes), 0) FROM cuota WHERE estado = 'pagada') AS suma_interes_pagado,
    (SELECT COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0)
     FROM movimiento_contable mc
     JOIN cuenta_contable cc ON cc.cuenta_contable_id = mc.cuenta_contable_id
     WHERE cc.codigo = '4201') AS saldo_4201,
    (SELECT COALESCE(SUM(interes), 0) FROM cuota WHERE estado = 'pagada')
    - (SELECT COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0)
       FROM movimiento_contable mc
       JOIN cuenta_contable cc ON cc.cuenta_contable_id = mc.cuenta_contable_id
       WHERE cc.codigo = '4201') AS diferencia;

-- 6) HU-Tarifario-Comisiones V8: Sigma monto de transacciones comision aplicadas debe ser
--    igual al saldo de la cuenta contable 4101 (Ingresos por comision): Sigma HABER - Sigma DEBE.
SELECT
    (SELECT COALESCE(SUM(monto), 0) FROM transaccion WHERE tipo = 'comision' AND estado = 'aplicada') AS suma_comisiones,
    (SELECT COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0)
     FROM movimiento_contable mc
     JOIN cuenta_contable cc ON cc.cuenta_contable_id = mc.cuenta_contable_id
     WHERE cc.codigo = '4101') AS saldo_4101,
    (SELECT COALESCE(SUM(monto), 0) FROM transaccion WHERE tipo = 'comision' AND estado = 'aplicada')
    - (SELECT COALESCE(SUM(CASE WHEN mc.tipo_movimiento = 'H' THEN mc.importe ELSE -mc.importe END), 0)
       FROM movimiento_contable mc
       JOIN cuenta_contable cc ON cc.cuenta_contable_id = mc.cuenta_contable_id
       WHERE cc.codigo = '4101') AS diferencia;
