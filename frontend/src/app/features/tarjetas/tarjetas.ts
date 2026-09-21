import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface TarjetaOut {
  tarjeta_id: number;
  cuenta_id: number;
  tipo_tarjeta: 'debito' | 'credito';
  ultimos_4: string;
  fecha_emision: string;
  fecha_vencimiento: string;
  estado: string;
}

/** Solo existe en la respuesta de /revelar: nunca se persiste ni se guarda en un servicio compartido. */
export interface TarjetaRevelada {
  pan: string;
  vencimiento: string;
  cvv: string;
  titular: string;
}

@Injectable({ providedIn: 'root' })
export class Tarjetas {
  private readonly http = inject(HttpClient);

  listar() {
    return this.http.get<TarjetaOut[]>(`${environment.apiUrl}/tarjetas`);
  }

  revelar(tarjetaId: number, password: string) {
    return this.http.post<TarjetaRevelada>(`${environment.apiUrl}/tarjetas/${tarjetaId}/revelar`, { password });
  }
}
