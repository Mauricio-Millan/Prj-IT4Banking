import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { PrestamoOut } from '../prestamos/prestamos';

export interface PrestamoRevisionOut extends PrestamoOut {
  cliente_id: number;
  codigo_cliente: string;
  cliente_nombre: string;
  cliente_documento: string;
}

export type DecisionPrestamo = 'aprobar' | 'rechazar';

export type EstadoPrestamoFiltro = 'todos' | PrestamoOut['estado'];

@Injectable({ providedIn: 'root' })
export class PrestamosRevision {
  private readonly http = inject(HttpClient);

  listarPendientes() {
    return this.http.get<PrestamoRevisionOut[]>(`${environment.apiUrl}/backoffice/prestamos`);
  }

  listarCartera(estado: EstadoPrestamoFiltro, codigoCliente?: string) {
    let params = new HttpParams().set('estado', estado);
    if (codigoCliente) params = params.set('codigo_cliente', codigoCliente);
    return this.http.get<PrestamoRevisionOut[]>(`${environment.apiUrl}/backoffice/prestamos`, { params });
  }

  resolver(id: number, decision: DecisionPrestamo) {
    return this.http.patch<PrestamoOut>(`${environment.apiUrl}/backoffice/prestamos/${id}`, { decision });
  }
}
