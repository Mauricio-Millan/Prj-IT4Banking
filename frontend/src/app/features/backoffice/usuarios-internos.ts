import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export type RolInterno = 'analista' | 'admin';

export interface UsuarioInternoOut {
  usuario_id: number;
  email: string;
  rol: RolInterno;
  activo: boolean;
  debe_cambiar_password: boolean;
  ultimo_acceso: string | null;
}

export interface UsuarioInternoIn {
  email: string;
  rol: RolInterno;
  password_temporal: string;
}

export interface ActualizarUsuarioInternoIn {
  activo?: boolean;
  rol?: RolInterno;
  password_temporal?: string;
}

@Injectable({ providedIn: 'root' })
export class UsuariosInternos {
  private readonly http = inject(HttpClient);

  listar() {
    return this.http.get<UsuarioInternoOut[]>(`${environment.apiUrl}/backoffice/usuarios`);
  }

  crear(datos: UsuarioInternoIn) {
    return this.http.post<UsuarioInternoOut>(`${environment.apiUrl}/backoffice/usuarios`, datos);
  }

  actualizar(usuarioId: number, datos: ActualizarUsuarioInternoIn) {
    return this.http.patch<UsuarioInternoOut>(`${environment.apiUrl}/backoffice/usuarios/${usuarioId}`, datos);
  }
}
