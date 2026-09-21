import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

/** Gemelo de backend/app/core/numeracion.py::digito_verificador (Luhn/mod-10). */
export function digitoVerificador(cuerpo: string): string {
  let suma = 0;
  const digitos = cuerpo.split('').reverse();
  for (let i = 0; i < digitos.length; i++) {
    let d = Number(digitos[i]) * (i % 2 === 0 ? 2 : 1);
    if (d > 9) d -= 9;
    suma += d;
  }
  return String((10 - (suma % 10)) % 10);
}

/** Ficticio — ver backend/app/core/config.py::banco_codigo_cce */
const BANCO_CODIGO_CCE = '099';

export function validarNumeroCuentaOCci(valor: string): string | null {
  const limpio = valor.replace(/[\s-]/g, '');
  if (!/^\d+$/.test(limpio) || (limpio.length !== 14 && limpio.length !== 20)) {
    return 'Número de cuenta o CCI inválido';
  }
  if (limpio.length === 14) {
    if (digitoVerificador(limpio.slice(0, -1)) !== limpio.slice(-1)) {
      return 'Número de cuenta inválido (dígito verificador)';
    }
    return null;
  }
  if (limpio.slice(0, 3) !== BANCO_CODIGO_CCE) {
    return 'Solo se admiten transferencias entre cuentas de este banco';
  }
  if (digitoVerificador(limpio.slice(0, 6)) !== limpio[18]) {
    return 'CCI inválido (dígito verificador de banco/oficina)';
  }
  if (digitoVerificador(limpio.slice(6, 18)) !== limpio[19]) {
    return 'CCI inválido (dígito verificador de cuenta)';
  }
  return null;
}

/** Validador reactivo para el campo de cuenta destino del formulario de transferencia. */
export function numeroCuentaValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    if (!control.value) return null; // required se declara aparte
    const mensaje = validarNumeroCuentaOCci(control.value);
    return mensaje ? { numeroCuenta: mensaje } : null;
  };
}
