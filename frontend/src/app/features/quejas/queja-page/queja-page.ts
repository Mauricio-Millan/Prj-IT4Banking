import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { QuejaOut, Quejas } from '../quejas';

@Component({
  selector: 'bc-queja-page',
  imports: [ReactiveFormsModule],
  templateUrl: './queja-page.html',
  styleUrl: './queja-page.scss',
})
export class QuejaPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(Quejas);

  protected readonly cargando = signal(true);
  protected readonly quejas = signal<QuejaOut[]>([]);
  protected readonly enviando = signal(false);
  protected readonly enviada = signal(false);
  protected readonly errorServidor = signal<string | null>(null);

  protected readonly form = this.fb.group({
    texto: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(2000)]],
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
    this.enviada.set(false);
    this.api.crear(this.form.getRawValue()).subscribe({
      next: () => {
        this.enviando.set(false);
        this.enviada.set(true);
        this.form.reset({ texto: '' });
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
