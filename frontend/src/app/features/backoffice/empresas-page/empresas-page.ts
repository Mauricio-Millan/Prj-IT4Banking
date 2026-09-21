import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { REGIONES } from '../../onboarding/onboarding';
import { rucValidator } from '../../../shared/validators/ruc';
import { ClienteEmpresaOut, ClientesEmpresa, EmpresaListadaOut } from '../clientes-empresa';

@Component({
  selector: 'bc-empresas-page',
  imports: [ReactiveFormsModule, DatePipe],
  templateUrl: './empresas-page.html',
  styleUrl: './empresas-page.scss',
})
export class EmpresasPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(ClientesEmpresa);

  protected readonly regiones = REGIONES;
  protected readonly cargando = signal(true);
  protected readonly error = signal(false);
  protected readonly empresas = signal<EmpresaListadaOut[]>([]);

  protected readonly enviando = signal(false);
  protected readonly errorCrear = signal<string | null>(null);
  protected readonly ultimaAlta = signal<ClienteEmpresaOut | null>(null);

  protected readonly form = this.fb.group({
    ruc: ['', [Validators.required, rucValidator()]],
    razon_social: ['', [Validators.required, Validators.minLength(3)]],
    representante_nombres: ['', [Validators.required, Validators.minLength(2)]],
    representante_apellidos: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
    telefono: [''],
    region: this.fb.control('Lima', Validators.required),
  });

  ngOnInit() {
    this.cargar();
  }

  private cargar() {
    this.cargando.set(true);
    this.error.set(false);
    this.api.listar().subscribe({
      next: e => {
        this.empresas.set(e);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set(true);
        this.cargando.set(false);
      },
    });
  }

  protected invalido(campo: string) {
    const c = this.form.get(campo);
    return !!c && c.invalid && c.touched;
  }

  protected crear() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.enviando.set(true);
    this.errorCrear.set(null);
    this.ultimaAlta.set(null);
    const { telefono, ...resto } = this.form.getRawValue();
    this.api.crear({ ...resto, telefono: telefono || null }).subscribe({
      next: empresa => {
        this.enviando.set(false);
        this.ultimaAlta.set(empresa);
        this.form.reset({ region: 'Lima' });
        this.cargar();
      },
      error: (e: HttpErrorResponse) => {
        this.enviando.set(false);
        this.errorCrear.set(
          e.status === 409 ? 'Ya existe una empresa con ese RUC o correo.' : 'Revisa los datos ingresados (RUC, razón social, correo).',
        );
      },
    });
  }
}
