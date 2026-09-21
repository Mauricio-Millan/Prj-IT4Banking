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
        auth.logout();
        router.navigate(['/login']);
      }
      return throwError(() => err);
    }),
  );
};
