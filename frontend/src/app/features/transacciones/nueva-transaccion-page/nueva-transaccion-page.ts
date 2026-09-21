import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AgruparDigitosPipe } from '../../../shared/pipes/agrupar-digitos.pipe';
import { numeroCuentaValidator } from '../../../shared/validators/luhn';
import { Cuentas, CuentaOut } from '../../cuentas/cuentas';
import { Transacciones, TipoTransaccion } from '../transacciones';

// Regla de exactitud monetaria: nunca <input type="number">. El string tal cual
// se manda en el JSON — Pydantic lo parsea a Decimal exacto, sin redondeo de punto flotante.
const PATRON_MONTO = /^\d{1,15}(\.\d{1,2})?$/;

@Component({
  selector: 'bc-nueva-transaccion-page',
  imports: [ReactiveFormsModule, RouterLink, AgruparDigitosPipe],
  templateUrl: './nueva-transaccion-page.html',
  styleUrl: './nueva-transaccion-page.scss',
})
export class NuevaTransaccionPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly cuentasApi = inject(Cuentas);
  private readonly api = inject(Transacciones);
  private readonly router = inject(Router);

  protected readonly cuentas = signal<CuentaOut[]>([]);
  protected readonly enviando = signal(false);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly form = this.fb.group({
    tipo: this.fb.control<TipoTransaccion>('deposito'),
    monto: ['', [Validators.required, Validators.pattern(PATRON_MONTO)]],
    cuenta_origen_id: this.fb.control<number | null>(null),
    // depósito: numero_cuenta propio elegido de un <select>; transferencia: numero_cuenta/cci tipeado a mano
    cuenta_destino_deposito: this.fb.control<string | null>(null),
    cuenta_destino_transferencia: ['', [numeroCuentaValidator()]],
  });

  ngOnInit() {
    this.cuentasApi.listar().subscribe(cuentas => {
      this.cuentas.set(cuentas);
      if (cuentas.length === 1) {
        this.form.patchValue({ cuenta_origen_id: cuentas[0].cuenta_id, cuenta_destino_deposito: cuentas[0].numero_cuenta });
      }
    });
  }

  protected invalido(campo: string) {
    const c = this.form.get(campo);
    return !!c && c.invalid && c.touched;
  }

  protected destinoTransferenciaInvalido() {
    if (this.form.value.tipo !== 'transferencia') return false;
    const c = this.form.get('cuenta_destino_transferencia')!;
    return !!c.value && c.invalid;
  }

  protected enviar() {
    const datos = this.form.getRawValue();
    const esDeposito = datos.tipo === 'deposito';
    const cuentaDestino = esDeposito ? datos.cuenta_destino_deposito : datos.cuenta_destino_transferencia;
    const faltaOrigen = !esDeposito && datos.cuenta_origen_id == null;
    const faltaDestino = !cuentaDestino;
    const destinoControl = esDeposito ? 'cuenta_destino_deposito' : 'cuenta_destino_transferencia';

    if (this.form.get('monto')!.invalid || this.form.get(destinoControl)!.invalid || faltaOrigen || faltaDestino) {
      this.form.markAllAsTouched();
      if (faltaOrigen) this.form.get('cuenta_origen_id')!.setErrors({ required: true });
      if (faltaDestino) this.form.get(destinoControl)!.setErrors({ required: true });
      return;
    }

    this.enviando.set(true);
    this.errorServidor.set(null);
    this.api.crear({ tipo: datos.tipo, monto: datos.monto, cuenta_origen_id: datos.cuenta_origen_id, cuenta_destino: cuentaDestino }).subscribe({
      next: () => this.router.navigate(['/cuentas']),
      error: (e: HttpErrorResponse) => {
        this.enviando.set(false);
        const detalle = e.error?.detail;
        this.errorServidor.set(typeof detalle === 'string' ? detalle : 'No pudimos completar la operación.');
      },
    });
  }
}
