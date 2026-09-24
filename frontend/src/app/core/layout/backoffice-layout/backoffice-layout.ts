import { Component, computed, inject } from '@angular/core';
import { Auth } from '../../auth/auth';
import { ClientLayout, ItemMenu } from '../client-layout/client-layout';

/** Shell interno (analista/admin): mismo shell, menu y titulo propios. */
@Component({
  selector: 'bc-backoffice-layout',
  imports: [ClientLayout],
  template: `<bc-client-layout titulo="Backoffice" inicio="/backoffice" loginRuta="/backoffice/login" [menu]="menu()" />`,
})
export class BackofficeLayout {
  private readonly auth = inject(Auth);

  // "Usuarios" solo para admin (matriz de permisos, HU-Gestion-Usuarios-Internos-Backoffice);
  // el backend vuelve a exigir el rol con roleGuard(['admin']) en la ruta, esto es solo UX.
  protected readonly menu = computed<ItemMenu[]>(() => [
    { ruta: '/backoffice/prestamos', etiqueta: 'Préstamos por aprobar' },
    { ruta: '/backoffice/prestamos/cartera', etiqueta: 'Cartera de préstamos' },
    { ruta: '/backoffice/quejas', etiqueta: 'Quejas por revisar' },
    ...(this.auth.rol() === 'admin'
      ? [
          { ruta: '/backoffice/clientes', etiqueta: 'Clientes' },
          { ruta: '/backoffice/empresas', etiqueta: 'Empresas' },
          { ruta: '/backoffice/usuarios', etiqueta: 'Usuarios' },
        ]
      : []),
    { ruta: '/cuentas', etiqueta: 'Vista cliente' },
  ]);
}
