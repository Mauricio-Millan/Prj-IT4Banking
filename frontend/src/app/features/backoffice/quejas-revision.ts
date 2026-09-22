import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export type CategoriaQueja = 'producto' | 'servicio' | 'fraude' | 'otro';

export interface QuejaRevisionOut {
  queja_id: number;
  cliente_id: number;
  codigo_cliente: string;
  cliente_documento: string;
  cliente_nombre: string;
  texto: string;
  categoria_sugerida: CategoriaQueja | null;
  confianza: string | null;
  motivo: string | null;
  prioridad: 'normal' | 'alta';
  estado_revision: 'pendiente' | 'confirmada' | 'corregida';
  creado_en: string;
}

export interface MetricasQuejasOut {
  total_revisadas: number;
  confirmadas: number;
  corregidas: number;
  porcentaje_acuerdo: number;
}

export const CATEGORIAS_QUEJA: CategoriaQueja[] = ['producto', 'servicio', 'fraude', 'otro'];

/** admin/analista — ver backend/app/routers/backoffice.py (rutas /quejas). */
@Injectable({ providedIn: 'root' })
export class QuejasRevision {
  private readonly http = inject(HttpClient);

  listarCola(categoria?: CategoriaQueja | null) {
    let params = new HttpParams();
    if (categoria) params = params.set('categoria', categoria);
    return this.http.get<QuejaRevisionOut[]>(`${environment.apiUrl}/backoffice/quejas`, { params });
  }

  resolver(quejaId: number, categoriaFinal: CategoriaQueja) {
    return this.http.patch(`${environment.apiUrl}/backoffice/quejas/${quejaId}`, { categoria_final: categoriaFinal });
  }

  metricas() {
    return this.http.get<MetricasQuejasOut>(`${environment.apiUrl}/backoffice/quejas/metricas`);
  }
}
