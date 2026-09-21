import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { environment } from '../../../../environments/environment';

function coincide(grupo: AbstractControl) {
  return grupo.get('nueva')?.value === grupo.get('confirmar')?.value ? null : { noCoincide: true };
}

/** V10/V11: primer acceso de personal interno con contrasena temporal, o cambio voluntario. */
@Component({
  selector: 'bc-cambiar-password-page',
  imports: [ReactiveFormsModule],
  templateUrl: './cambiar-password-page.html',
  styleUrl: './cambiar-password-page.scss',
})
export class CambiarPasswordPage {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  protected readonly enviando = signal(false);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly form = this.fb.group(
    {
      actual: ['', Validators.required],
      nueva: ['', [Validators.required, Validators.minLength(12)]],
      confirmar: ['', Validators.required],
    },
    { validators: [coincide] },
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
    const { actual, nueva } = this.form.getRawValue();
    this.enviando.set(true);
    this.errorServidor.set(null);
    this.http.post(`${environment.apiUrl}/auth/cambiar-password`, { actual, nueva }).subscribe({
      next: () => this.router.navigate(['/backoffice/prestamos']),
      error: (e: HttpErrorResponse) => {
        this.enviando.set(false);
        this.errorServidor.set(
          e.status === 401 ? 'Tu contraseña actual no es correcta.' : (e.error?.detail ?? 'No pudimos cambiar tu contraseña.'),
        );
      },
    });
  }
}
