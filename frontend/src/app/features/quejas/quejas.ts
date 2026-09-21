import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface QuejaIn {
  texto: string;
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
