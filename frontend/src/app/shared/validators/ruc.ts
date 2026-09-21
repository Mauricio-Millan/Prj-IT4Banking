import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

/** Gemelo de backend/app/core/ruc.py::ruc_valido (algoritmo estandar SUNAT). */
export function rucValido(ruc: string): boolean {
  if (!(ruc.length === 11 && /^\d+$/.test(ruc) && ruc.startsWith('20'))) return false;
  const pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
  let suma = 0;
  for (let i = 0; i < 10; i++) suma += Number(ruc[i]) * pesos[i];
  const resto = suma % 11;
  let dv = 11 - resto;
  if (dv === 10) dv = 0;
  else if (dv === 11) dv = 1;
  return dv === Number(ruc[10]);
}

export function rucValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    if (!control.value) return null; // required se declara aparte
    return rucValido(control.value) ? null : { ruc: true };
  };
}
