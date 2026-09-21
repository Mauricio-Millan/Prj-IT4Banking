"""Validacion de RUC peruano (algoritmo estandar SUNAT). Solo se aceptan RUC que empiezan en
'20' (persona juridica): un RUC '10' (persona natural con negocio) no es una empresa para
HU-Segmentacion-Clientes."""


def ruc_valido(ruc: str) -> bool:
    if not (len(ruc) == 11 and ruc.isdigit() and ruc.startswith("20")):
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(d) * p for d, p in zip(ruc[:10], pesos))
    resto = suma % 11
    dv = 11 - resto
    dv = {10: 0, 11: 1}.get(dv, dv)
    return dv == int(ruc[10])
