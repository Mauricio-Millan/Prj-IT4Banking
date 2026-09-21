import { Routes, UrlMatcher, UrlSegment } from '@angular/router';
import { authGuard } from './core/auth/auth-guard';
import { invitadoGuard } from './core/auth/invitado-guard';
import { roleGuard } from './core/auth/role-guard';
import { AuthLayout } from './core/layout/auth-layout/auth-layout';
import { BackofficeLayout } from './core/layout/backoffice-layout/backoffice-layout';
import { ClientLayout } from './core/layout/client-layout/client-layout';

/**
 * Layout architecture: tres shells, cada uno con su guard y sus features lazy.
 *   /                          → LandingPage     (publico, sin sesion; con sesion → /cuentas)
 *   /login, /registro          → AuthLayout      (publico)
 *   /cuentas, /tarjetas, ...   → ClientLayout    (rol cliente o superior)
 *   /backoffice/...            → BackofficeLayout (rol analista | admin)
 */

const PRIMER_SEGMENTO_CONOCIDO = new Set([
  'login', 'registro', 'cuentas', 'transacciones', 'tarjetas', 'prestamos', 'quejas', 'backoffice', 'tarifas',
]);

// canMatch se evalua ANTES de intentar los hijos: authGuard en ClientLayout (path:'') intercepta
// CUALQUIER primer segmento desconocido (no solo 'cuentas') y redirige a /login antes de que un
// wildcard de cierre tenga oportunidad. Este matcher solo activa el catch-all cuando el primer
// segmento no es uno de los ya usados por otra ruta, para no competir con ellas.
const rutaDesconocida: UrlMatcher = (segments: UrlSegment[]) =>
  segments.length > 0 && !PRIMER_SEGMENTO_CONOCIDO.has(segments[0].path) ? { consumed: segments } : null;

export const routes: Routes = [
  // Debe ir primero: un path:'' con hijos (AuthLayout, mas abajo) le "gana" a un bare '/' en
  // Angular incluso sin hijo que matchee (renderiza el shell con el outlet vacio y NO sigue
  // probando rutas hermanas, porque no le quedan segmentos pendientes por resolver). Por eso
  // el landing solo se alcanza si esta ANTES, con pathMatch:'full' para no capturar /login ni /registro.
  {
    path: '',
    pathMatch: 'full',
    canMatch: [invitadoGuard],
    loadComponent: () => import('./features/landing/landing-page/landing-page').then(m => m.LandingPage),
  },
  {
    path: '',
    component: AuthLayout,
    children: [
      { path: 'login', loadComponent: () => import('./features/login/login-page/login-page').then(m => m.LoginPage) },
      { path: 'registro', loadComponent: () => import('./features/onboarding/onboarding-page/onboarding-page').then(m => m.OnboardingPage) },
      // Fuera del arbol roleGuard'd de BackofficeLayout a proposito: un visitante sin sesion
      // (o un cliente que aterriza aqui por error) debe poder ver el login/cambio de contrasena.
      { path: 'backoffice/login', loadComponent: () => import('./features/backoffice/backoffice-login-page/backoffice-login-page').then(m => m.BackofficeLoginPage) },
      { path: 'backoffice/cambiar-password', loadComponent: () => import('./features/backoffice/cambiar-password-page/cambiar-password-page').then(m => m.CambiarPasswordPage) },
    ],
  },
  // Debe ir ANTES de ClientLayout/backoffice: el orden del arreglo es el orden de intento, y
  // authGuard/roleGuard redirigirian (via UrlTree) cualquier primer segmento desconocido antes
  // de que esta ruta tuviera oportunidad si quedara despues. El matcher excluye los segmentos
  // de las rutas de abajo, asi que no compite con ellas pese a ir primero.
  {
    matcher: rutaDesconocida,
    canMatch: [invitadoGuard],
    loadComponent: () => import('./features/landing/landing-page/landing-page').then(m => m.LandingPage),
  },
  // Publica, sin guard: la HU exige que un visitante sin sesion Y un cliente ya autenticado
  // puedan verla igual (enlazada desde el pie de la landing y desde el menu del cliente).
  { path: 'tarifas', loadComponent: () => import('./features/tarifario/tarifas-page/tarifas-page').then(m => m.TarifasPage) },
  {
    path: '',
    component: ClientLayout,
    canMatch: [authGuard],
    children: [
      { path: 'cuentas', loadChildren: () => import('./features/cuentas/cuentas.routes').then(m => m.CUENTAS_ROUTES) },
      { path: 'transacciones/nueva', loadComponent: () => import('./features/transacciones/nueva-transaccion-page/nueva-transaccion-page').then(m => m.NuevaTransaccionPage) },
      { path: 'tarjetas', loadComponent: () => import('./features/tarjetas/tarjetas-page/tarjetas-page').then(m => m.TarjetasPage) },
      { path: 'prestamos', loadComponent: () => import('./features/prestamos/prestamos-page/prestamos-page').then(m => m.PrestamosPage) },
      { path: 'prestamos/:id/cronograma', loadComponent: () => import('./features/prestamos/cronograma-page/cronograma-page').then(m => m.CronogramaPage) },
      { path: 'quejas', loadComponent: () => import('./features/quejas/queja-page/queja-page').then(m => m.QuejaPage) },
    ],
  },
  {
    path: 'backoffice',
    component: BackofficeLayout,
    canMatch: [roleGuard(['analista', 'admin'])],
    loadChildren: () => import('./features/backoffice/backoffice.routes').then(m => m.BACKOFFICE_ROUTES),
  },
  // Ultimo recurso: primer segmento conocido pero ruta anidada invalida (ej. /cuentas/x/y/z).
  { path: '**', redirectTo: '/cuentas' },
];
