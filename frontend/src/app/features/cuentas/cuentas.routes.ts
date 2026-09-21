import { Routes } from '@angular/router';

export const CUENTAS_ROUTES: Routes = [
  { path: '', loadComponent: () => import('./cuentas-page/cuentas-page').then(m => m.CuentasPage) },
  { path: ':id/movimientos', loadComponent: () => import('./movimientos-page/movimientos-page').then(m => m.MovimientosPage) },
];
