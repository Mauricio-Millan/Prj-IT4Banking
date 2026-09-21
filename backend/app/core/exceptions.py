class RecursoNoEncontrado(Exception):
    """No existe o no pertenece al cliente autenticado — misma respuesta para ambos casos (RNF-09)."""


class SaldoInsuficiente(Exception):
    pass


class AsientoDesbalanceado(Exception):
    """Defensa en profundidad: no deberia ocurrir si el service arma el asiento bien;
    si el trigger SQL la dispara (en Azure SQL/SQL Server), es un bug del codigo, no un
    error de negocio del usuario. Ver trg_asiento_balanceado en la migracion."""
