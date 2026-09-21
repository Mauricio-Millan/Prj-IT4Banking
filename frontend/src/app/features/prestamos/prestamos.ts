import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface SolicitudPrestamoIn {
  monto_original: string; // igual que monto en transacciones: string exacto, nunca number
  plazo: number;
  cuenta_id: number;
}

export interface ProximaCuotaOut {
  numero: number;
  fecha_vencimiento: string;
  total: string;
  estado: 'pendiente' | 'vencida';
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
  cuenta_desembolso_numero: string | null;
  cuotas_total: number;
  cuotas_pagadas: number;
  proxima_cuota: ProximaCuotaOut | null;
}

export interface CuotaOut {
  cuota_id: number;
  numero: number;
  fecha_vencimiento: string;
  capital: string;
  interes: string;
  total: string;
  saldo_capital_despues: string;
  estado: 'pendiente' | 'pagada' | 'vencida';
  fecha_pago: string | null;
  transaccion_id: number | null;
}

export interface MontoConceptoOut {
  monto: string;
  concepto: string;
}

export interface PagoOut {
  cuota: CuotaOut;
  transaccion_id: number;
  penalidad: MontoConceptoOut | null;
  total_debitado: string;
  saldo_capital: string;
  estado_prestamo: string;
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

  cronograma(prestamoId: number) {
    return this.http.get<CuotaOut[]>(`${environment.apiUrl}/prestamos/${prestamoId}/cronograma`);
  }

  pagar(prestamoId: number, cuentaOrigenId: number) {
    return this.http.post<PagoOut>(`${environment.apiUrl}/prestamos/${prestamoId}/pagos`, { cuenta_origen_id: cuentaOrigenId });
  }
}
