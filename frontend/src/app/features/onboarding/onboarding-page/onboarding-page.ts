import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Auth } from '../../../core/auth/auth';
import { TarjetaOut } from '../../tarjetas/tarjetas';
import { Onboarding, REGIONES, RegistroIn } from '../onboarding';

const DOC_PATRON: Record<string, RegExp> = {
  DNI: /^\d{8}$/,
  CE: /^[A-Za-z0-9]{9,12}$/,
  PASAPORTE: /^[A-Za-z0-9]{6,20}$/,
};

function documentoValido(grupo: AbstractControl) {
  const tipo = grupo.get('tipo_documento')?.value as string;
  const num = (grupo.get('numero_documento')?.value as string) ?? '';
  return DOC_PATRON[tipo]?.test(num) ? null : { documento: true };
}

function mayorDeEdad(c: AbstractControl) {
  if (!c.value) return null;
  const n = new Date(c.value);
  const hoy = new Date();
  const edad = hoy.getFullYear() - n.getFullYear() - (hoy < new Date(hoy.getFullYear(), n.getMonth(), n.getDate()) ? 1 : 0);
  return edad >= 18 ? null : { menor: true };
}

function coincide(grupo: AbstractControl) {
  return grupo.get('password')?.value === grupo.get('confirmar')?.value ? null : { noCoincide: true };
}

/** RF-01 onboarding autoservicio. Cada campo escribe una columna de `cliente` (toggle de linaje). */
@Component({
  selector: 'bc-onboarding-page',
  imports: [ReactiveFormsModule, RouterLink, DatePipe],
  templateUrl: './onboarding-page.html',
  styleUrl: './onboarding-page.scss',
})
export class OnboardingPage {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(Onboarding);
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  protected readonly regiones = REGIONES;
  protected readonly linaje = signal(false);
  protected readonly enviando = signal(false);
  protected readonly errorServidor = signal<string | null>(null);
  /** Al llegar la respuesta la sesion ya arranco (iniciarSesionCon); esto solo retiene
   * la navegacion a /cuentas hasta que el cliente confirme haber visto su tarjeta. */
  protected readonly tarjetaEmitida = signal<TarjetaOut | null>(null);

  protected readonly form = this.fb.group(
    {
      tipo_documento: this.fb.control<'DNI' | 'CE' | 'PASAPORTE'>('DNI'),
      numero_documento: ['', Validators.required],
      nombres: ['', [Validators.required, Validators.minLength(2)]],
      apellidos: ['', [Validators.required, Validators.minLength(2)]],
      fecha_nacimiento: ['', [Validators.required, mayorDeEdad]],
      email: ['', [Validators.required, Validators.email]],
      telefono: ['', Validators.pattern(/^\+?[\d\s]{6,20}$/)],
      region: ['Lima', Validators.required],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmar: ['', Validators.required],
    },
    { validators: [documentoValido, coincide] },
  );

  protected invalido(campo: string) {
    const c = this.form.get(campo);
    return !!c && c.invalid && c.touched;
  }

  protected enviar() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { confirmar: _, telefono, ...resto } = this.form.getRawValue();
    const datos: RegistroIn = { ...resto, telefono: telefono || null };

    this.enviando.set(true);
    this.errorServidor.set(null);
    this.api.registrar(datos).subscribe({
      next: r => {
        this.auth.iniciarSesionCon(r.access_token);
        this.enviando.set(false);
        this.tarjetaEmitida.set(r.tarjeta);
      },
      error: (e: HttpErrorResponse) => {
        this.enviando.set(false);
        const detalle = e.error?.detail;
        if (e.status === 409 && detalle?.campo) {
          this.form.get(detalle.campo)?.setErrors({ duplicado: true });
          this.form.get(detalle.campo)?.markAsTouched();
        } else {
          this.errorServidor.set('No pudimos completar el registro. Inténtalo de nuevo.');
        }
      },
    });
  }

  protected continuar() {
    this.router.navigate(['/cuentas']);
  }
}
