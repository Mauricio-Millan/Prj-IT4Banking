import { Pipe, PipeTransform } from '@angular/core';

/** Muestra un número de cuenta/CCI en grupos de 4 dígitos: "00110384726119" -> "0011 0384 7261 19". */
@Pipe({ name: 'agruparDigitos' })
export class AgruparDigitosPipe implements PipeTransform {
  transform(valor: string | null | undefined): string {
    if (!valor) return '';
    return valor.replace(/(\d{4})(?=\d)/g, '$1 ');
  }
}
