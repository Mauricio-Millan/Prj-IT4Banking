import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { Auth } from './auth';

/** Protege un arbol de rutas completo (layout + hijos): sin sesion valida → /login. */
export const authGuard: CanMatchFn = () => {
  const auth = inject(Auth);
  return auth.autenticado() ? true : inject(Router).createUrlTree(['/login']);
};
