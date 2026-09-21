import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TarjetaDigital } from '../tarjeta-digital/tarjeta-digital';
import { Tarjetas, TarjetaOut, TarjetaRevelada } from '../tarjetas';

@Component({
  selector: 'bc-tarjetas-page',
  imports: [DatePipe, ReactiveFormsModule, TarjetaDigital],
  templateUrl: './tarjetas-page.html',
  styleUrl: './tarjetas-page.scss',
})
export class TarjetasPage implements OnInit {
  private readonly api = inject(Tarjetas);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly tarjetas = signal<TarjetaOut[]>([]);

  // Modal de contrasena: nada de esto (ni el resultado revelado) toca localStorage/sessionStorage
  // ni un servicio compartido — vive solo en signals de esta pagina, ver HU-Tarjeta-Datos-Cifrados-Revelar.
  protected readonly modalTarjetaId = signal<number | null>(null);
  protected readonly passwordForm = this.fb.group({ password: ['', Validators.required] });
  protected readonly revelando = signal(false);
  protected readonly errorRevelado = signal<string | null>(null);
  protected readonly bloqueado = signal(false);
  protected readonly revelado = signal<{ tarjetaId: number; datos: TarjetaRevelada } | null>(null);

  ngOnInit() {
    this.api.listar().subscribe({
      next: t => {
        this.tarjetas.set(t);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }

  protected abrirModal(tarjetaId: number) {
    this.modalTarjetaId.set(tarjetaId);
    this.passwordForm.reset();
    this.errorRevelado.set(null);
    this.bloqueado.set(false);
  }

  protected cerrarModal() {
    this.modalTarjetaId.set(null);
  }

  protected confirmarPassword() {
    const tarjetaId = this.modalTarjetaId();
    if (tarjetaId === null || this.passwordForm.invalid) {
      this.passwordForm.markAllAsTouched();
      return;
    }
    this.revelando.set(true);
    this.errorRevelado.set(null);
    this.api.revelar(tarjetaId, this.passwordForm.getRawValue().password).subscribe({
      next: datos => {
        this.revelando.set(false);
        this.revelado.set({ tarjetaId, datos });
        this.cerrarModal();
      },
      error: (e: HttpErrorResponse) => {
        this.revelando.set(false);
        if (e.status === 429) {
          this.bloqueado.set(true);
          this.errorRevelado.set('Demasiados intentos, espera 15 minutos.');
        } else {
          this.errorRevelado.set('Contraseña incorrecta.');
        }
      },
    });
  }

  protected cerrarTarjetaDigital() {
    this.revelado.set(null);
  }
}
