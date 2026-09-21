import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { Auth } from './auth';

/** Espejo de authGuard: protege la landing publica. Con sesion valida → /cuentas, no ve marketing. */
export const invitadoGuard: CanMatchFn = () => {
  const auth = inject(Auth);
  return auth.autenticado() ? inject(Router).createUrlTree(['/cuentas']) : true;
};
