import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Auth } from '../../../core/auth/auth';

@Component({
  selector: 'bc-login-page',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './login-page.html',
  styleUrl: './login-page.scss',
})
export class LoginPage {
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
      next: () => this.router.navigate([this.auth.rol() === 'cliente' ? '/cuentas' : '/backoffice']),
      error: () => {
        this.enviando.set(false);
        // mensaje generico a proposito: no se revela si el email existe o si fue la clave (anti-enumeracion)
        this.errorServidor.set('Correo o contraseña incorrectos.');
      },
    });
  }
}
