import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { Auth, Rol } from './auth';

/** roleGuard(['analista','admin']) — el rol viene del JWT; el backend vuelve a validarlo. */
export const roleGuard = (roles: Rol[]): CanMatchFn => () => {
  const auth = inject(Auth);
  const rol = auth.rol();
  if (auth.autenticado() && rol && roles.includes(rol)) return true;
  return inject(Router).createUrlTree([auth.autenticado() ? '/cuentas' : '/login']);
};
