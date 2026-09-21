import { Routes } from '@angular/router';
import { roleGuard } from '../../core/auth/role-guard';

export const BACKOFFICE_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'prestamos' },
  { path: 'prestamos', loadComponent: () => import('./prestamos-revision-page/prestamos-revision-page').then(m => m.PrestamosRevisionPage) },
  { path: 'quejas', loadComponent: () => import('./quejas-revision-page/quejas-revision-page').then(m => m.QuejasRevisionPage) },
  {
    path: 'usuarios',
    canMatch: [roleGuard(['admin'])],
    loadComponent: () => import('./usuarios-page/usuarios-page').then(m => m.UsuariosPage),
  },
  {
    path: 'clientes',
    canMatch: [roleGuard(['admin'])],
    loadComponent: () => import('./clientes-page/clientes-page').then(m => m.ClientesPage),
  },
  // 'resumenes' se agrega con RF-10
];
