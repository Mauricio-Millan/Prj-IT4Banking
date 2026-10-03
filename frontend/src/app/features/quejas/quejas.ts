import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export type TipoLegalQueja = 'reclamo' | 'queja';

export interface QuejaIn {
  texto: string;
  tipo_legal?: TipoLegalQueja;
  pedido_consumidor?: string | null;
  // string, nunca number — mismo criterio que TransaccionIn.monto (Pydantic parsea el texto exacto)
  monto_reclamado?: string | null;
  fecha_incidente?: string | null;
  cuenta_id?: number | null;
  tarjeta_id?: number | null;
  prestamo_id?: number | null;
  transaccion_id?: number | null;
}

export interface QuejaOut {
  queja_id: number;
  texto: string;
  categoria_sugerida: string | null;
  categoria_final: string | null;
  estado_revision: 'pendiente' | 'confirmada' | 'corregida';
  creado_en: string;
}

@Injectable({ providedIn: 'root' })
export class Quejas {
  private readonly http = inject(HttpClient);

  crear(datos: QuejaIn) {
    return this.http.post<QuejaOut>(`${environment.apiUrl}/quejas`, datos);
  }

  listar() {
    return this.http.get<QuejaOut[]>(`${environment.apiUrl}/quejas`);
  }
}
