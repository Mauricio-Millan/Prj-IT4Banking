import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export type CategoriaQueja = 'producto' | 'servicio' | 'fraude' | 'otro';
export type EstadoQueja = 'pendiente' | 'confirmada' | 'corregida';
export type EstadoQuejaFiltro = 'todos' | EstadoQueja;

export interface QuejaRevisionOut {
  queja_id: number;
  cliente_id: number;
  codigo_cliente: string;
  cliente_documento: string;
  cliente_nombre: string;
  texto: string;
  categoria_sugerida: CategoriaQueja | null;
  categoria_final: CategoriaQueja | null;
  confianza: string | null;
  motivo: string | null;
  resumen: string | null;
  prioridad: 'normal' | 'alta';
  estado_revision: EstadoQueja;
  revisado_por_email: string | null;
  creado_en: string;
  revisado_en: string | null;
  modelo_ia: string | null;
  senal_vulnerabilidad: boolean | null;
  senal_amenaza_escalamiento: boolean | null;
  tipo_legal: 'reclamo' | 'queja';
  pedido_consumidor: string | null;
  monto_reclamado: string | null;
  fecha_incidente: string | null;
  referencia: string | null;
}

export interface MetricasQuejasOut {
  total_pendientes: number;
  prioridad_alta_pendientes: number;
  total_revisadas: number;
  confirmadas: number;
  corregidas: number;
  porcentaje_acuerdo: number;
  confianza_promedio: number | null;
  tiempo_promedio_revision_horas: number | null;
}

export const CATEGORIAS_QUEJA: CategoriaQueja[] = ['producto', 'servicio', 'fraude', 'otro'];

/** admin/analista — ver backend/app/routers/backoffice.py (rutas /quejas). */
@Injectable({ providedIn: 'root' })
export class QuejasRevision {
  private readonly http = inject(HttpClient);

  listarCola(estado: EstadoQuejaFiltro = 'pendiente', categoria?: CategoriaQueja | null) {
    let params = new HttpParams().set('estado', estado);
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
