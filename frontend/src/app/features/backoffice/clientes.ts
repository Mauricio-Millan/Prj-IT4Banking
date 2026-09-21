import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { CuentaOut } from '../cuentas/cuentas';

export interface ClienteConCuentasOut {
  cliente_id: number;
  codigo_cliente: string;
  tipo_documento: string;
  numero_documento: string;
  nombres: string;
  apellidos: string;
  email: string;
  telefono: string | null;
  region: string;
  segmento: string;
  estado: string;
  es_empleado: boolean;
  fecha_alta: string;
  cuentas: CuentaOut[];
}

export interface ClientesPagina {
  items: ClienteConCuentasOut[];
  total: number;
  pagina: number;
  tamano: number;
}

/** Excepcion admin-only a V14 (HU-Gestion-Usuarios-Internos-Backoffice): ver services/clientes.py. */
@Injectable({ providedIn: 'root' })
export class BackofficeClientes {
  private readonly http = inject(HttpClient);

  listar(pagina = 1, tamano = 20) {
    const params = new HttpParams().set('pagina', pagina).set('tamano', tamano);
    return this.http.get<ClientesPagina>(`${environment.apiUrl}/backoffice/clientes`, { params });
  }
}
