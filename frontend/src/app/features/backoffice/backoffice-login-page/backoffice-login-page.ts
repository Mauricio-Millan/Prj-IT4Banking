import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Auth } from '../../../core/auth/auth';

/** Entrada de backoffice, separada de /login: un cliente que llega aqui no inicia sesion. */
@Component({
  selector: 'bc-backoffice-login-page',
  imports: [ReactiveFormsModule],
  templateUrl: './backoffice-login-page.html',
  styleUrl: './backoffice-login-page.scss',
})
export class BackofficeLoginPage {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  protected readonly enviando = signal(false);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  protected invalido(campo: string) {
    const c = this.form.get(campo);
    return !!c && c.invalid && c.touched;
  }

  protected enviar() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { email, password } = this.form.getRawValue();
    this.enviando.set(true);
    this.errorServidor.set(null);
    this.auth.login(email, password).subscribe({
      next: r => {
        this.enviando.set(false);
        if (this.auth.rol() === 'cliente') {
          // "Esta entrada es solo para personal del banco": no se inicia sesion de cliente aqui.
          this.auth.logout();
          this.errorServidor.set('Esta entrada es solo para personal del banco.');
          return;
        }
        this.router.navigate([r.debe_cambiar_password ? '/backoffice/cambiar-password' : '/backoffice/prestamos']);
      },
      error: () => {
        this.enviando.set(false);
        this.errorServidor.set('Correo o contraseña incorrectos.');
      },
    });
  }
}
