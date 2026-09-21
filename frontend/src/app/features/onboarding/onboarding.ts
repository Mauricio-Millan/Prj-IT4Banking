import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { TarjetaOut } from '../tarjetas/tarjetas';

export interface RegistroIn {
  tipo_documento: 'DNI' | 'CE' | 'PASAPORTE';
  numero_documento: string;
  nombres: string;
  apellidos: string;
  fecha_nacimiento: string;
  email: string;
  telefono: string | null;
  region: string;
  password: string;
}

export interface RegistroOut {
  access_token: string;
  cliente_id: number;
  codigo_cliente: string;
  cuenta_id: number;
  numero_cuenta: string;
  segmento: string;
  tarjeta: TarjetaOut;
}

/** Misma lista que backend/app/schemas/auth.py::REGIONES */
export const REGIONES = [
  'Amazonas', 'Áncash', 'Apurímac', 'Arequipa', 'Ayacucho', 'Cajamarca', 'Callao', 'Cusco',
  'Huancavelica', 'Huánuco', 'Ica', 'Junín', 'La Libertad', 'Lambayeque', 'Lima', 'Loreto',
  'Madre de Dios', 'Moquegua', 'Pasco', 'Piura', 'Puno', 'San Martín', 'Tacna', 'Tumbes', 'Ucayali',
] as const;

@Injectable({ providedIn: 'root' })
export class Onboarding {
  private readonly http = inject(HttpClient);

  registrar(datos: RegistroIn) {
    return this.http.post<RegistroOut>(`${environment.apiUrl}/auth/registro`, datos);
  }
}
