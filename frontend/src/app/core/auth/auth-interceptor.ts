import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { Auth } from './auth';

/** Adjunta el JWT a cada llamada a la API y cierra sesion ante un 401. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(Auth);
  const router = inject(Router);
  const token = auth.tokenActual();

  const conToken = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(conToken).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !req.url.endsWith('/auth/login')) {
        // Un usuario interno desactivado (V7) cae aqui con un JWT aun vigente: el interceptor
        // debe devolverlo a SU login, no al de clientes.
        const enBackoffice = router.url.startsWith('/backoffice');
        auth.logout();
        router.navigate([enBackoffice ? '/backoffice/login' : '/login']);
      }
      return throwError(() => err);
    }),
  );
};
