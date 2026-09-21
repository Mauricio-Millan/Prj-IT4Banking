import { Component, inject, OnInit, signal } from '@angular/core';
import { DecisionPrestamo, PrestamoRevisionOut, PrestamosRevision } from '../prestamos-revision';

@Component({
  selector: 'bc-prestamos-revision-page',
  imports: [],
  templateUrl: './prestamos-revision-page.html',
  styleUrl: './prestamos-revision-page.scss',
})
export class PrestamosRevisionPage implements OnInit {
  private readonly api = inject(PrestamosRevision);

  protected readonly cargando = signal(true);
  protected readonly pendientes = signal<PrestamoRevisionOut[]>([]);
  protected readonly procesando = signal<number | null>(null);

  ngOnInit() {
    this.cargar();
  }

  protected resolver(id: number, decision: DecisionPrestamo) {
    this.procesando.set(id);
    this.api.resolver(id, decision).subscribe({
      next: () => {
        this.procesando.set(null);
        this.cargar();
      },
      error: () => this.procesando.set(null),
    });
  }

  private cargar() {
    this.cargando.set(true);
    this.api.listarPendientes().subscribe({
      next: p => {
        this.pendientes.set(p);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
  }
}
