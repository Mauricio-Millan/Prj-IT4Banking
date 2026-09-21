import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AgruparDigitosPipe } from '../../../shared/pipes/agrupar-digitos.pipe';
import { Cuentas, CuentaOut } from '../cuentas';

const ETIQUETA_TIPO: Record<string, string> = { ahorro: 'Cuenta de ahorro', corriente: 'Cuenta corriente' };

@Component({
  selector: 'bc-cuentas-page',
  imports: [RouterLink, CurrencyPipe, DatePipe, AgruparDigitosPipe],
  templateUrl: './cuentas-page.html',
  styleUrl: './cuentas-page.scss',
})
export class CuentasPage implements OnInit {
  private readonly api = inject(Cuentas);

  protected readonly etiquetaTipo: Record<string, string> = ETIQUETA_TIPO;
  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly cuentas = signal<CuentaOut[]>([]);

  protected readonly totales = computed(() => {
    const acc: Record<string, number> = {};
    for (const c of this.cuentas()) {
      acc[c.moneda] = (acc[c.moneda] ?? 0) + Number(c.saldo); // agregacion solo para mostrar, no se reenvia al servidor
    }
    return Object.entries(acc);
  });

  ngOnInit() {
    this.cargar();
  }

  private cargar() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.listar().subscribe({
      next: cuentas => {
        this.cuentas.set(cuentas);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }
}
