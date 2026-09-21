import { Component, inject, input, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Auth } from '../../auth/auth';

export interface ItemMenu {
  ruta: string;
  etiqueta: string;
}

/**
 * Shell autenticado: nav "isla" flotante + contenido.
 * BackofficeLayout lo reutiliza pasando otro menu y titulo.
 */
@Component({
  selector: 'bc-client-layout',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './client-layout.html',
  styleUrl: './client-layout.scss',
})
export class ClientLayout {
  protected readonly auth = inject(Auth);
  private readonly router = inject(Router);

  readonly titulo = input('BancoCloud');
  readonly inicio = input('/cuentas');
  readonly loginRuta = input('/login');
  readonly menu = input<ItemMenu[]>([
    { ruta: '/cuentas', etiqueta: 'Cuentas' },
    { ruta: '/tarjetas', etiqueta: 'Tarjetas' },
    { ruta: '/prestamos', etiqueta: 'Préstamos' },
    { ruta: '/quejas', etiqueta: 'Quejas' },
  ]);

  protected readonly abierto = signal(false);

  protected alternar() {
    this.abierto.update(v => !v);
  }

  protected cerrar() {
    this.abierto.set(false);
  }

  protected salir() {
    this.auth.logout();
    this.router.navigate([this.loginRuta()]);
  }
}
