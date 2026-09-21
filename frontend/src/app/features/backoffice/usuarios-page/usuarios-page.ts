import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { RolInterno, UsuarioInternoOut, UsuariosInternos } from '../usuarios-internos';

@Component({
  selector: 'bc-usuarios-page',
  imports: [DatePipe, ReactiveFormsModule, FormsModule],
  templateUrl: './usuarios-page.html',
  styleUrl: './usuarios-page.scss',
})
export class UsuariosPage implements OnInit {
  private readonly api = inject(UsuariosInternos);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly usuarios = signal<UsuarioInternoOut[]>([]);

  protected readonly crearForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    rol: this.fb.control<RolInterno>('analista'),
    password_temporal: ['', [Validators.required, Validators.minLength(12)]],
  });
  protected readonly creando = signal(false);
  protected readonly errorCrear = signal<string | null>(null);

  // fila cuya "resetear temporal" esta abierta, y su valor tipeado
  protected readonly resetAbierto = signal<number | null>(null);
  protected readonly nuevaTemporal = signal('');
  protected readonly errorFila = signal<{ id: number; mensaje: string } | null>(null);

  ngOnInit() {
    this.cargar();
  }

  private cargar() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.listar().subscribe({
      next: u => {
        this.usuarios.set(u);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }

  protected crear() {
    if (this.crearForm.invalid) {
      this.crearForm.markAllAsTouched();
      return;
    }
    this.creando.set(true);
    this.errorCrear.set(null);
    this.api.crear(this.crearForm.getRawValue()).subscribe({
      next: u => {
        this.usuarios.update(lista => [...lista, u]);
        this.creando.set(false);
        this.crearForm.reset({ rol: 'analista' });
      },
      error: (e: HttpErrorResponse) => {
        this.creando.set(false);
        this.errorCrear.set(
          e.status === 409 ? 'Ya existe un usuario con ese correo.' : 'Revisa el correo (debe ser @bancocloud.pe) y la temporal (mín. 12 caracteres).',
        );
      },
    });
  }

  protected alternarActivo(u: UsuarioInternoOut) {
    this.errorFila.set(null);
    this.api.actualizar(u.usuario_id, { activo: !u.activo }).subscribe({
      next: actualizado => this.reemplazar(actualizado),
      error: (e: HttpErrorResponse) => this.mostrarErrorFila(u.usuario_id, e),
    });
  }

  protected cambiarRol(u: UsuarioInternoOut, rol: RolInterno) {
    if (rol === u.rol) return;
    this.errorFila.set(null);
    this.api.actualizar(u.usuario_id, { rol }).subscribe({
      next: actualizado => this.reemplazar(actualizado),
      error: (e: HttpErrorResponse) => this.mostrarErrorFila(u.usuario_id, e),
    });
  }

  protected abrirReset(usuarioId: number) {
    this.resetAbierto.set(usuarioId);
    this.nuevaTemporal.set('');
    this.errorFila.set(null);
  }

  protected confirmarReset(u: UsuarioInternoOut) {
    const temporal = this.nuevaTemporal();
    if (temporal.length < 12) {
      this.mostrarErrorFila(u.usuario_id, null, 'La temporal debe tener al menos 12 caracteres.');
      return;
    }
    this.api.actualizar(u.usuario_id, { password_temporal: temporal }).subscribe({
      next: actualizado => {
        this.reemplazar(actualizado);
        this.resetAbierto.set(null);
      },
      error: (e: HttpErrorResponse) => this.mostrarErrorFila(u.usuario_id, e),
    });
  }

  private reemplazar(actualizado: UsuarioInternoOut) {
    this.usuarios.update(lista => lista.map(u => (u.usuario_id === actualizado.usuario_id ? actualizado : u)));
  }

  private mostrarErrorFila(id: number, e: HttpErrorResponse | null, mensajeManual?: string) {
    const mensaje = mensajeManual ?? (typeof e?.error?.detail === 'string' ? e.error.detail : 'No se pudo completar la acción.');
    this.errorFila.set({ id, mensaje });
  }
}
