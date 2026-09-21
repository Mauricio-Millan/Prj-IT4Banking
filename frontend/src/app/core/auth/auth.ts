import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';

export type Rol = 'cliente' | 'analista' | 'admin';

interface Claims {
  sub: string;
  rol: Rol;
  exp: number;
}

const TOKEN_KEY = 'bc.token';

@Injectable({ providedIn: 'root' })
export class Auth {
  private readonly http = inject(HttpClient);
  private readonly token = signal<string | null>(leerToken());

  readonly claims = computed(() => decodificar(this.token()));
  readonly autenticado = computed(() => {
    const c = this.claims();
    return !!c && c.exp * 1000 > Date.now();
  });
  readonly rol = computed(() => this.claims()?.rol ?? null);

  tokenActual(): string | null {
    return this.token();
  }

  login(email: string, password: string) {
    return this.http
      .post<{ access_token: string; debe_cambiar_password: boolean }>(`${environment.apiUrl}/auth/login`, { email, password })
      .pipe(tap(r => this.guardar(r.access_token)));
  }

  logout() {
    this.guardar(null);
  }

  /** El registro (RF-01) ya devuelve un JWT: se inicia sesion sin pasar por login. */
  iniciarSesionCon(token: string) {
    this.guardar(token);
  }

  private guardar(token: string | null) {
    this.token.set(token);
    try {
      token ? sessionStorage.setItem(TOKEN_KEY, token) : sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* sessionStorage no disponible (modo privado): la sesion vive solo en memoria */
    }
  }
}

function leerToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function decodificar(token: string | null): Claims | null {
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}
