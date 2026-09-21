import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AgruparDigitosPipe } from '../../../shared/pipes/agrupar-digitos.pipe';
import { Cuentas, MovimientosPagina, SaldoOut } from '../cuentas';

const TAMANO = 20;

const ETIQUETA_TIPO: Record<string, string> = {
  deposito: 'Depósito', retiro: 'Retiro', transferencia: 'Transferencia',
  pago_prestamo: 'Pago de préstamo', comision: 'Comisión', desembolso: 'Desembolso de préstamo',
};

@Component({
  selector: 'bc-movimientos-page',
  imports: [RouterLink, ReactiveFormsModule, CurrencyPipe, DatePipe, AgruparDigitosPipe],
  templateUrl: './movimientos-page.html',
  styleUrl: './movimientos-page.scss',
})
export class MovimientosPage {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(Cuentas);
  private readonly fb = inject(FormBuilder).nonNullable;

  // ponytail: ActivatedRoute manual en vez de withComponentInputBinding() global — ese flag
  // rompe ClientLayout (tambien enrutado y con inputs propios titulo/inicio/menu del mismo shape).
  private readonly paramMap = toSignal(this.route.paramMap);
  readonly id = computed(() => this.paramMap()?.get('id') ?? '');

  protected readonly etiquetaTipo = ETIQUETA_TIPO;
  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly saldo = signal<SaldoOut | null>(null);
  protected readonly pagina = signal(1);
  protected readonly datos = signal<MovimientosPagina | null>(null);

  protected readonly filtro = this.fb.group({ desde: [''], hasta: [''] });

  constructor() {
    // effect (no un fetch de una sola vez): Angular puede reusar esta instancia al navegar
    // de /cuentas/1/movimientos a /cuentas/2/movimientos, hay que reaccionar a cambios de id()/pagina().
    effect(() => {
      const cuentaId = Number(this.id());
      const p = this.pagina();
      this.cargar(cuentaId, p);
    });
  }

  protected buscar() {
    this.pagina.set(1);
    this.cargar(Number(this.id()), 1);
  }

  protected irAPagina(p: number) {
    this.pagina.set(p);
  }

  private cargar(cuentaId: number, pagina: number) {
    this.cargando.set(true);
    this.error.set(false);
    const { desde, hasta } = this.filtro.getRawValue();

    this.api.saldo(cuentaId).subscribe({ next: s => this.saldo.set(s), error: () => this.error.set(true) });
    this.api.movimientos(cuentaId, { desde: desde || undefined, hasta: hasta || undefined }, pagina, TAMANO).subscribe({
      next: d => {
        this.datos.set(d);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }
}
