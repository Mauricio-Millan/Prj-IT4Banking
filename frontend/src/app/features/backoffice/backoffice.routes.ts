import { Routes } from '@angular/router';

export const BACKOFFICE_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'prestamos' },
  { path: 'prestamos', loadComponent: () => import('./prestamos-revision-page/prestamos-revision-page').then(m => m.PrestamosRevisionPage) },
  { path: 'quejas', loadComponent: () => import('./quejas-revision-page/quejas-revision-page').then(m => m.QuejasRevisionPage) },
  // 'resumenes' se agrega con RF-10
];
