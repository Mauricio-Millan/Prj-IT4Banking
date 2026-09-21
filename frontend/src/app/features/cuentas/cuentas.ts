import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

/** saldo/monto llegan como string exacto — ver backend/app/schemas/comunes.py::Dinero */
export interface CuentaOut {
  cuenta_id: number;
  numero_cuenta: string;
  cci: string;
  tipo_cuenta: 'ahorro' | 'corriente';
  moneda: 'PEN' | 'USD';
  saldo: string;
  fecha_apertura: string;
  estado: string;
}

export interface SaldoOut {
  cuenta_id: number;
  numero_cuenta: string;
  moneda: string;
  saldo: string;
}

export interface MovimientoOut {
  transaccion_id: number;
  fecha_hora: string;
  tipo: string;
  monto: string;
  canal: string;
  estado: string;
  direccion: 'entrada' | 'salida';
  cuenta_origen_id: number | null;
  cuenta_destino_id: number | null;
  cuenta_origen_numero: string | null;
  cuenta_destino_numero: string | null;
}

export interface MovimientosPagina {
  items: MovimientoOut[];
  total: number;
  pagina: number;
  tamano: number;
}

@Injectable({ providedIn: 'root' })
export class Cuentas {
  private readonly http = inject(HttpClient);

  listar() {
    return this.http.get<CuentaOut[]>(`${environment.apiUrl}/cuentas`);
  }

  saldo(cuentaId: number) {
    return this.http.get<SaldoOut>(`${environment.apiUrl}/cuentas/${cuentaId}/saldo`);
  }

  movimientos(cuentaId: number, opts: { desde?: string; hasta?: string }, pagina = 1, tamano = 20) {
    let params = new HttpParams().set('pagina', pagina).set('tamano', tamano);
    if (opts.desde) params = params.set('desde', opts.desde);
    if (opts.hasta) params = params.set('hasta', opts.hasta);
    return this.http.get<MovimientosPagina>(`${environment.apiUrl}/cuentas/${cuentaId}/movimientos`, { params });
  }
}
