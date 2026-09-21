import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { BackofficeClientes, ClienteConCuentasOut } from '../clientes';

const TAMANO = 20;

@Component({
  selector: 'bc-clientes-page',
  imports: [CurrencyPipe, DatePipe],
  templateUrl: './clientes-page.html',
  styleUrl: './clientes-page.scss',
})
export class ClientesPage implements OnInit {
  private readonly api = inject(BackofficeClientes);

  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly clientes = signal<ClienteConCuentasOut[]>([]);
  protected readonly total = signal(0);
  protected readonly pagina = signal(1);
  protected readonly tamano = TAMANO;

  ngOnInit() {
    this.cargar();
  }

  protected irAPagina(p: number) {
    this.pagina.set(p);
    this.cargar();
  }

  private cargar() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.listar(this.pagina(), this.tamano).subscribe({
      next: r => {
        this.clientes.set(r.items);
        this.total.set(r.total);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }
}
