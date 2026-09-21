import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { TarjetaOut } from '../tarjetas/tarjetas';

export interface ClienteEmpresaIn {
  ruc: string;
  razon_social: string;
  representante_nombres: string;
  representante_apellidos: string;
  email: string;
  telefono: string | null;
  region: string;
}

export interface ClienteEmpresaOut {
  cliente_id: number;
  codigo_cliente: string;
  ruc: string;
  razon_social: string;
  cuenta_id: number;
  numero_cuenta: string;
  cci: string;
  password_temporal: string;
  tarjeta: TarjetaOut;
}

export interface EmpresaListadaOut {
  cliente_id: number;
  codigo_cliente: string;
  ruc: string;
  razon_social: string;
  region: string;
  fecha_alta: string;
  estado: string;
}

/** admin-only — ver backend/app/routers/backoffice.py::crear_cliente_empresa/listar_clientes_empresa. */
@Injectable({ providedIn: 'root' })
export class ClientesEmpresa {
  private readonly http = inject(HttpClient);

  crear(datos: ClienteEmpresaIn) {
    return this.http.post<ClienteEmpresaOut>(`${environment.apiUrl}/backoffice/clientes-empresa`, datos);
  }

  listar() {
    return this.http.get<EmpresaListadaOut[]>(`${environment.apiUrl}/backoffice/clientes-empresa`);
  }
}
