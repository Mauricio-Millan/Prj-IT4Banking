import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface SolicitudPrestamoIn {
  monto_original: string; // igual que monto en transacciones: string exacto, nunca number
  plazo: number;
}

export interface PrestamoOut {
  prestamo_id: number;
  monto_original: string;
  saldo_capital: string;
  tasa: string;
  plazo: number;
  fecha_desembolso: string | null;
  fecha_vencimiento: string | null;
  dias_mora: number;
  bucket_mora: string;
  estado: 'solicitado' | 'aprobado' | 'rechazado' | 'vigente' | 'cancelado';
}

@Injectable({ providedIn: 'root' })
export class Prestamos {
  private readonly http = inject(HttpClient);

  solicitar(datos: SolicitudPrestamoIn) {
    return this.http.post<PrestamoOut>(`${environment.apiUrl}/prestamos/solicitudes`, datos);
  }

  listar() {
    return this.http.get<PrestamoOut[]>(`${environment.apiUrl}/prestamos`);
  }
}
