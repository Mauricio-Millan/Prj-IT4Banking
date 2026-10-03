import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CuentaOut, Cuentas, MovimientoOut } from '../../cuentas/cuentas';
import { Prestamos, PrestamoOut } from '../../prestamos/prestamos';
import { Tarjetas, TarjetaOut } from '../../tarjetas/tarjetas';
import { QuejaOut, Quejas } from '../quejas';

type TipoReferencia = 'ninguna' | 'cuenta' | 'tarjeta' | 'prestamo' | 'transaccion';

// Misma regla de exactitud monetaria que en nueva-transaccion-page: nunca <input type="number">.
const PATRON_MONTO = /^\d{1,15}(\.\d{1,2})?$/;

@Component({
  selector: 'bc-queja-page',
  imports: [ReactiveFormsModule],
  templateUrl: './queja-page.html',
  styleUrl: './queja-page.scss',
})
export class QuejaPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(Quejas);
  private readonly cuentasApi = inject(Cuentas);
  private readonly tarjetasApi = inject(Tarjetas);
  private readonly prestamosApi = inject(Prestamos);

  protected readonly hoy = new Date().toISOString().slice(0, 10);

  protected readonly cargando = signal(true);
  protected readonly quejas = signal<QuejaOut[]>([]);
  protected readonly enviando = signal(false);
  protected readonly enviada = signal(false);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly cuentas = signal<CuentaOut[]>([]);
  protected readonly tarjetas = signal<TarjetaOut[]>([]);
  protected readonly prestamos = signal<PrestamoOut[]>([]);
  protected readonly transacciones = signal<MovimientoOut[]>([]);
  protected readonly cargandoTransacciones = signal(false);

  protected readonly form = this.fb.group({
    texto: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(2000)]],
    tipoLegal: this.fb.control<'reclamo' | 'queja'>('reclamo'),
    pedidoConsumidor: ['', [Validators.maxLength(500)]],
    montoReclamado: ['', [Validators.pattern(PATRON_MONTO)]],
    fechaIncidente: [''],
    tipoReferencia: this.fb.control<TipoReferencia>('ninguna'),
    referenciaId: this.fb.control<number | null>(null),
  });

  ngOnInit() {
    this.cargar();
    this.cuentasApi.listar().subscribe(c => this.cuentas.set(c));
    this.tarjetasApi.listar().subscribe(t => this.tarjetas.set(t));
    this.prestamosApi.listar().subscribe(p => this.prestamos.set(p));

    this.form.get('tipoReferencia')!.valueChanges.subscribe(tipo => {
      this.form.patchValue({ referenciaId: null });
      if (tipo === 'transaccion' && this.transacciones().length === 0) this.cargarTransacciones();
    });
  }

  private cargarTransacciones() {
    this.cargandoTransacciones.set(true);
    this.cuentasApi.listar().subscribe(cuentas => {
      if (cuentas.length === 0) {
        this.cargandoTransacciones.set(false);
        return;
      }
      let pendientes = cuentas.length;
      const todas: MovimientoOut[] = [];
      for (const c of cuentas) {
        this.cuentasApi.movimientos(c.cuenta_id, {}, 1, 20).subscribe({
          next: pagina => {
            todas.push(...pagina.items);
            if (--pendientes === 0) {
              this.transacciones.set(todas.sort((a, b) => b.fecha_hora.localeCompare(a.fecha_hora)));
              this.cargandoTransacciones.set(false);
            }
          },
          error: () => { if (--pendientes === 0) this.cargandoTransacciones.set(false); },
        });
      }
    });
  }

  protected invalido(campo: string) {
    const c = this.form.get(campo);
    return !!c && c.invalid && c.touched;
  }

  protected etiquetaTransaccion(t: MovimientoOut): string {
    const fecha = new Date(t.fecha_hora).toLocaleDateString('es-PE');
    return `${t.tipo} · S/ ${t.monto} · ${fecha}`;
  }

  protected enviar() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const datos = this.form.getRawValue();
    this.enviando.set(true);
    this.errorServidor.set(null);
    this.enviada.set(false);
    this.api.crear({
      texto: datos.texto,
      tipo_legal: datos.tipoLegal,
      pedido_consumidor: datos.pedidoConsumidor || null,
      monto_reclamado: datos.montoReclamado || null,
      fecha_incidente: datos.fechaIncidente || null,
      cuenta_id: datos.tipoReferencia === 'cuenta' ? datos.referenciaId : null,
      tarjeta_id: datos.tipoReferencia === 'tarjeta' ? datos.referenciaId : null,
      prestamo_id: datos.tipoReferencia === 'prestamo' ? datos.referenciaId : null,
      transaccion_id: datos.tipoReferencia === 'transaccion' ? datos.referenciaId : null,
    }).subscribe({
      next: () => {
        this.enviando.set(false);
        this.enviada.set(true);
        this.form.reset({ texto: '', tipoLegal: 'reclamo', tipoReferencia: 'ninguna', referenciaId: null });
        this.cargar();
      },
      error: () => {
        this.enviando.set(false);
        this.errorServidor.set('No pudimos registrar tu queja. Intenta de nuevo.');
      },
    });
  }

  private cargar() {
    this.api.listar().subscribe({
      next: q => {
        this.quejas.set(q);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false),
    });
  }
}
