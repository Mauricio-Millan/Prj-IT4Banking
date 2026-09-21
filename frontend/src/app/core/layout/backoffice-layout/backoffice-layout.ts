import { Component } from '@angular/core';
import { ClientLayout, ItemMenu } from '../client-layout/client-layout';

/** Shell interno (analista/admin): mismo shell, menu y titulo propios. */
@Component({
  selector: 'bc-backoffice-layout',
  imports: [ClientLayout],
  template: `<bc-client-layout titulo="Backoffice" inicio="/backoffice" [menu]="menu" />`,
})
export class BackofficeLayout {
  protected readonly menu: ItemMenu[] = [
    { ruta: '/backoffice/prestamos', etiqueta: 'Préstamos por aprobar' },
    { ruta: '/backoffice/quejas', etiqueta: 'Quejas por revisar' },
    { ruta: '/cuentas', etiqueta: 'Vista cliente' },
  ];
}
