import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { PrestamoOut } from '../prestamos/prestamos';

export interface PrestamoRevisionOut extends PrestamoOut {
  cliente_id: number;
  cliente_nombre: string;
  cliente_documento: string;
}

export type DecisionPrestamo = 'aprobar' | 'rechazar';

@Injectable({ providedIn: 'root' })
export class PrestamosRevision {
  private readonly http = inject(HttpClient);

  listarPendientes() {
    return this.http.get<PrestamoRevisionOut[]>(`${environment.apiUrl}/backoffice/prestamos`);
  }

  resolver(id: number, decision: DecisionPrestamo) {
    return this.http.patch<PrestamoOut>(`${environment.apiUrl}/backoffice/prestamos/${id}`, { decision });
  }
}
