import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter, UrlTree } from '@angular/router';
import { Auth } from './auth';
import { invitadoGuard } from './invitado-guard';

describe('invitadoGuard', () => {
  let auth: Auth;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter([])] });
    auth = TestBed.inject(Auth);
  });

  function ejecutar() {
    return TestBed.runInInjectionContext(() => invitadoGuard({} as any, [] as any));
  }

  it('sin sesion permite ver la landing', () => {
    spyOn(auth, 'autenticado').and.returnValue(false);
    expect(ejecutar()).toBe(true);
  });

  it('con sesion redirige a /cuentas', () => {
    spyOn(auth, 'autenticado').and.returnValue(true);
    const resultado = ejecutar();
    expect(resultado instanceof UrlTree).toBeTrue();
    expect((resultado as UrlTree).toString()).toBe('/cuentas');
  });
});
