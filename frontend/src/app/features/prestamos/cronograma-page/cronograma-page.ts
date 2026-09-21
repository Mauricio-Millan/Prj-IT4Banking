import { CurrencyPipe, DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CuentaOut, Cuentas } from '../../cuentas/cuentas';
import { Tarifario } from '../../tarifario/tarifario';
import { CuotaOut, Prestamos } from '../prestamos';

@Component({
  selector: 'bc-cronograma-page',
  imports: [CurrencyPipe, DatePipe, RouterLink, FormsModule],
  templateUrl: './cronograma-page.html',
  styleUrl: './cronograma-page.scss',
})
export class CronogramaPage implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(Prestamos);
  private readonly cuentasApi = inject(Cuentas);
  private readonly tarifarioApi = inject(Tarifario);

  private readonly prestamoId = Number(this.route.snapshot.paramMap.get('id'));

  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly cuotas = signal<CuotaOut[]>([]);
  protected readonly cuentas = signal<CuentaOut[]>([]);
  protected readonly montoPenalidad = signal<string | null>(null);

  protected readonly primeraImpaga = computed(() => this.cuotas().find(c => c.estado !== 'pagada') ?? null);

  protected readonly modalAbierto = signal(false);
  protected readonly cuentaSeleccionada = signal<number | null>(null);
  protected readonly pagando = signal(false);
  protected readonly errorPago = signal<string | null>(null);

  ngOnInit() {
    this.cargarCronograma();
    this.cuentasApi.listar().subscribe(cuentas => {
      this.cuentas.set(cuentas);
      const propias = cuentas.filter(c => c.moneda === 'PEN');
      if (propias.length === 1) this.cuentaSeleccionada.set(propias[0].cuenta_id);
    });
    this.tarifarioApi.obtener().subscribe(t => {
      const preAtr = t.tarifas.find(x => x.codigo === 'PRE-ATR');
      if (preAtr) this.montoPenalidad.set(preAtr.monto);
    });
  }

  private cargarCronograma() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.cronograma(this.prestamoId).subscribe({
      next: cuotas => {
        this.cuotas.set(cuotas);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }

  protected abrirPago() {
    this.modalAbierto.set(true);
    this.errorPago.set(null);
  }

  protected cerrarPago() {
    this.modalAbierto.set(false);
  }

  protected totalAPagar(): string | null {
    const cuota = this.primeraImpaga();
    if (!cuota) return null;
    if (cuota.estado === 'vencida' && this.montoPenalidad()) {
      return (Number(cuota.total) + Number(this.montoPenalidad())).toFixed(2);
    }
    return cuota.total;
  }

  protected confirmarPago() {
    const cuentaId = this.cuentaSeleccionada();
    if (cuentaId === null) return;
    this.pagando.set(true);
    this.errorPago.set(null);
    this.api.pagar(this.prestamoId, cuentaId).subscribe({
      next: resultado => {
        this.pagando.set(false);
        this.modalAbierto.set(false);
        this.cuotas.update(lista => lista.map(c => (c.cuota_id === resultado.cuota.cuota_id ? resultado.cuota : c)));
      },
      error: (e: HttpErrorResponse) => {
        this.pagando.set(false);
        const detalle = e.error?.detail;
        this.errorPago.set(typeof detalle === 'string' ? detalle : 'No pudimos procesar el pago.');
      },
    });
  }
}
