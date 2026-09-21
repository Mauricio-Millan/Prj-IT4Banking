import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export type TipoTransaccion = 'deposito' | 'retiro' | 'transferencia';

export interface TransaccionIn {
  tipo: TipoTransaccion;
  // string, nunca number: se manda el texto exacto que escribio el usuario, sin pasar por Number()
  monto: string;
  cuenta_origen_id: number | null;
  // numero_cuenta (14 digitos) o cci (20 digitos) de destino, nunca un id interno
  cuenta_destino: string | null;
}

export interface TransaccionOut {
  transaccion_id: number;
  fecha_hora: string;
  tipo: string;
  monto: string;
  canal: string;
  estado: string;
  cuenta_origen_id: number | null;
  cuenta_destino_id: number | null;
  cuenta_origen_numero: string | null;
  cuenta_destino_numero: string | null;
}

@Injectable({ providedIn: 'root' })
export class Transacciones {
  private readonly http = inject(HttpClient);

  crear(datos: TransaccionIn) {
    return this.http.post<TransaccionOut>(`${environment.apiUrl}/transacciones`, datos);
  }
}
