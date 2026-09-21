import { CurrencyPipe, DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CuentaOut, Cuentas } from '../../cuentas/cuentas';
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
  imports: [ReactiveFormsModule, CurrencyPipe, DatePipe, RouterLink],
  templateUrl: './prestamos-page.html',
  styleUrl: './prestamos-page.scss',
})
export class PrestamosPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(Prestamos);
  private readonly cuentasApi = inject(Cuentas);

  protected readonly mensajeResultado = MENSAJE_RESULTADO;
  protected readonly cargando = signal(true);
  protected readonly prestamos = signal<PrestamoOut[]>([]);
  protected readonly cuentas = signal<CuentaOut[]>([]);
  protected readonly enviando = signal(false);
  protected readonly resultado = signal<PrestamoOut | null>(null);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly form = this.fb.group({
    monto_original: ['', [Validators.required, Validators.pattern(PATRON_MONTO)]],
    plazo: [12, [Validators.required, Validators.min(1), Validators.max(60)]],
    cuenta_id: this.fb.control<number | null>(null, Validators.required),
  });

  ngOnInit() {
    this.cargar();
    this.cuentasApi.listar().subscribe(cuentas => {
      this.cuentas.set(cuentas);
      const cuentasPen = cuentas.filter(c => c.moneda === 'PEN');
      if (cuentasPen.length === 1) this.form.patchValue({ cuenta_id: cuentasPen[0].cuenta_id });
    });
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
    const { monto_original, plazo, cuenta_id } = this.form.getRawValue();
    this.api.solicitar({ monto_original, plazo, cuenta_id: cuenta_id! }).subscribe({
      next: p => {
        this.enviando.set(false);
        this.resultado.set(p);
        this.form.reset({ monto_original: '', plazo: 12, cuenta_id: this.form.value.cuenta_id });
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
