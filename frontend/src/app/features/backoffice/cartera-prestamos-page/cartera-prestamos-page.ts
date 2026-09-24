import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EstadoPrestamoFiltro, PrestamoRevisionOut, PrestamosRevision } from '../prestamos-revision';

const ESTADOS: { valor: EstadoPrestamoFiltro; etiqueta: string }[] = [
  { valor: 'todos', etiqueta: 'Todos' },
  { valor: 'solicitado', etiqueta: 'Solicitado' },
  { valor: 'vigente', etiqueta: 'Vigente' },
  { valor: 'cancelado', etiqueta: 'Cancelado' },
  { valor: 'rechazado', etiqueta: 'Rechazado' },
];

@Component({
  selector: 'bc-cartera-prestamos-page',
  imports: [FormsModule, RouterLink],
  templateUrl: './cartera-prestamos-page.html',
  styleUrl: './cartera-prestamos-page.scss',
})
export class CarteraPrestamosPage {
  private readonly api = inject(PrestamosRevision);

  protected readonly estados = ESTADOS;
  protected readonly estado = signal<EstadoPrestamoFiltro>('todos');
  protected readonly codigoCliente = signal('');
  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly cartera = signal<PrestamoRevisionOut[]>([]);

  constructor() {
    this.buscar();
  }

  protected buscar() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.listarCartera(this.estado(), this.codigoCliente().trim() || undefined).subscribe({
      next: filas => {
        this.cartera.set(filas);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }
}
