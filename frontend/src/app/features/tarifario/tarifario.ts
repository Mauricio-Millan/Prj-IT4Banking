import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface TarifaOut {
  codigo: string;
  nombre: string;
  monto: string;
  moneda: string;
  gratis_por_mes: number | null;
  vigente_desde: string;
}

export interface TarifarioOut {
  tarifas: TarifaOut[];
  nota_itf: string;
}

/** Publico, sin JWT — ver backend/app/routers/tarifario.py. */
@Injectable({ providedIn: 'root' })
export class Tarifario {
  private readonly http = inject(HttpClient);

  obtener() {
    return this.http.get<TarifarioOut>(`${environment.apiUrl}/tarifario`);
  }
}
