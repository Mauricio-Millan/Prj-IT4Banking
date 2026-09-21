import { CurrencyPipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Tarifario, TarifarioOut } from '../tarifario';

@Component({
  selector: 'bc-tarifas-page',
  imports: [CurrencyPipe, RouterLink],
  templateUrl: './tarifas-page.html',
  styleUrl: './tarifas-page.scss',
})
export class TarifasPage implements OnInit {
  private readonly api = inject(Tarifario);

  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly tarifario = signal<TarifarioOut | null>(null);

  ngOnInit() {
    this.api.obtener().subscribe({
      next: t => {
        this.tarifario.set(t);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }
}
