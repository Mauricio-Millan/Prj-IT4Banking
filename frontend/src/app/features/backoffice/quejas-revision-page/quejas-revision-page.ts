import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  CATEGORIAS_QUEJA,
  CategoriaQueja,
  MetricasQuejasOut,
  QuejaRevisionOut,
  QuejasRevision,
} from '../quejas-revision';

// Record<string, string> (no Record<CategoriaQueja, string>): las tarjetas se renderizan vía
// ng-template + ngTemplateOutlet (reuso entre tablero por estado y por categoria), cuyo contexto
// Angular tipa como `any` -- indexar con una clave `any` un Record de union estricta es un error
// de TS (ts7053) aunque el valor en runtime siempre sea una CategoriaQueja valida.
const ETIQUETA_CATEGORIA: Record<string, string> = {
  producto: 'Producto', servicio: 'Servicio', fraude: 'Fraude', otro: 'Otro',
};

/**
 * Extension 2026-09-29: tablero Kanban por estado_revision, sin drag-and-drop. Una sola
 * llamada con estado=todos; pendientes()/confirmadas()/corregidas() son computed() sobre la
 * misma señal cola() -- resolver() actualiza el item en el arreglo (no lo elimina), asi el
 * siguiente render lo ubica solo en su nueva columna.
 */
@Component({
  selector: 'bc-quejas-revision-page',
  imports: [DatePipe, FormsModule, NgTemplateOutlet],
  templateUrl: './quejas-revision-page.html',
  styleUrl: './quejas-revision-page.scss',
})
export class QuejasRevisionPage implements OnInit {
  private readonly api = inject(QuejasRevision);

  protected readonly categorias = CATEGORIAS_QUEJA;
  protected readonly etiquetaCategoria = ETIQUETA_CATEGORIA;

  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly cola = signal<QuejaRevisionOut[]>([]);
  protected readonly metricas = signal<MetricasQuejasOut | null>(null);
  protected readonly filtroCategoria = signal<CategoriaQueja | null>(null);

  protected readonly pendientes = computed(() => this.cola().filter(q => q.estado_revision === 'pendiente'));
  protected readonly confirmadas = computed(() => this.cola().filter(q => q.estado_revision === 'confirmada'));
  protected readonly corregidas = computed(() => this.cola().filter(q => q.estado_revision === 'corregida'));

  // Extension 2026-10-02: tablero Kanban adicional, agrupado por categoria_sugerida. Puramente
  // client-side sobre la misma cola() ya cargada con estado=todos -- sin llamadas de red nuevas.
  protected readonly agrupacion = signal<'estado' | 'categoria'>('estado');
  protected readonly porCategoria = computed(() => {
    const grupos: Record<CategoriaQueja | 'sin_clasificar', QuejaRevisionOut[]> =
      { producto: [], servicio: [], fraude: [], otro: [], sin_clasificar: [] };
    for (const q of this.cola()) {
      grupos[q.categoria_sugerida ?? 'sin_clasificar'].push(q);
    }
    return grupos;
  });

  protected readonly seleccion = signal<Record<number, CategoriaQueja>>({});
  protected readonly resolviendo = signal<number | null>(null);
  protected readonly errorFila = signal<{ id: number; mensaje: string } | null>(null);
  protected readonly detalle = signal<QuejaRevisionOut | null>(null);

  ngOnInit() {
    this.cargar();
    this.cargarMetricas();
  }

  protected aplicarFiltro(categoria: string) {
    this.filtroCategoria.set((categoria as CategoriaQueja) || null);
    this.cargar();
  }

  private cargar() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.listarCola('todos', this.filtroCategoria()).subscribe({
      next: cola => {
        this.cola.set(cola);
        const seleccionInicial: Record<number, CategoriaQueja> = {};
        for (const q of cola) if (q.estado_revision === 'pendiente') seleccionInicial[q.queja_id] = q.categoria_sugerida ?? 'otro';
        this.seleccion.set(seleccionInicial);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }

  private cargarMetricas() {
    this.api.metricas().subscribe(m => this.metricas.set(m));
  }

  protected elegirCategoria(quejaId: number, categoria: string) {
    this.seleccion.update(s => ({ ...s, [quejaId]: categoria as CategoriaQueja }));
  }

  protected etiquetaBoton(queja: QuejaRevisionOut): string {
    const elegida = this.seleccion()[queja.queja_id];
    return elegida === queja.categoria_sugerida ? 'Mover a confirmada' : 'Mover a corregida';
  }

  protected verDetalle(queja: QuejaRevisionOut) {
    this.detalle.set(queja);
  }

  protected cerrarDetalle() {
    this.detalle.set(null);
  }

  protected resolver(queja: QuejaRevisionOut) {
    const categoriaFinal = this.seleccion()[queja.queja_id];
    this.resolviendo.set(queja.queja_id);
    this.errorFila.set(null);
    this.api.resolver(queja.queja_id, categoriaFinal).subscribe({
      next: () => {
        this.resolviendo.set(null);
        const nuevoEstado = categoriaFinal === queja.categoria_sugerida ? 'confirmada' : 'corregida';
        this.cola.update(lista => lista.map(q => q.queja_id === queja.queja_id
          ? { ...q, estado_revision: nuevoEstado, categoria_final: categoriaFinal }
          : q));
        this.cargarMetricas();
      },
      error: (e: HttpErrorResponse) => {
        this.resolviendo.set(null);
        this.errorFila.set({ id: queja.queja_id, mensaje: e.status === 409 ? 'Esta queja ya fue revisada.' : 'No se pudo guardar la decisión.' });
      },
    });
  }
}
