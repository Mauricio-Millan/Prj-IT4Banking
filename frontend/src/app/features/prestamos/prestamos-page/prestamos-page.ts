import { CurrencyPipe, DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { PrestamoOut, Prestamos } from '../prestamos';

const PATRON_MONTO = /^\d{1,15}(\.\d{1,2})?$/;

const MENSAJE_RESULTADO: Record<PrestamoOut['estado'], string> = {
  vigente: '¡Aprobado! El monto ya está disponible en tu cuenta.',
  rechazado: 'No cumples los requisitos para este préstamo en este momento.',
  solicitado: 'Tu solicitud fue enviada a revisión. Te avisaremos cuando sea evaluada.',
  aprobado: 'Tu solicitud fue aprobada.',
  cancelado: 'Tu solicitud fue cancelada.',
};

@Component({
  selector: 'bc-prestamos-page',
  imports: [ReactiveFormsModule, CurrencyPipe, DatePipe],
  templateUrl: './prestamos-page.html',
  styleUrl: './prestamos-page.scss',
})
export class PrestamosPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(Prestamos);

  protected readonly mensajeResultado = MENSAJE_RESULTADO;
  protected readonly cargando = signal(true);
  protected readonly prestamos = signal<PrestamoOut[]>([]);
  protected readonly enviando = signal(false);
  protected readonly resultado = signal<PrestamoOut | null>(null);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly form = this.fb.group({
    monto_original: ['', [Validators.required, Validators.pattern(PATRON_MONTO)]],
    plazo: [12, [Validators.required, Validators.min(1), Validators.max(60)]],
  });

  ngOnInit() {
    this.cargar();
  }

  protected invalido(campo: string) {
    const c = this.form.get(campo);
    return !!c && c.invalid && c.touched;
  }

  protected enviar() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.enviando.set(true);
    this.errorServidor.set(null);
    this.resultado.set(null);
    this.api.solicitar(this.form.getRawValue()).subscribe({
      next: p => {
        this.enviando.set(false);
        this.resultado.set(p);
        this.form.reset({ monto_original: '', plazo: 12 });
        this.cargar();
      },
      error: (e: HttpErrorResponse) => {
        this.enviando.set(false);
        const detalle = e.error?.detail;
        this.errorServidor.set(typeof detalle === 'string' ? detalle : 'No pudimos procesar tu solicitud.');
      },
    });
  }

  private cargar() {
    this.api.listar().subscribe({
      next: p => {
        this.prestamos.set(p);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
  }
}
