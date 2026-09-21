import { Component, DestroyRef, inject, input, OnInit, output, signal } from '@angular/core';
import { AgruparDigitosPipe } from '../../../shared/pipes/agrupar-digitos.pipe';
import { TarjetaRevelada } from '../tarjetas';

const SEGUNDOS_VISIBLE = 30;

@Component({
  selector: 'bc-tarjeta-digital',
  imports: [AgruparDigitosPipe],
  templateUrl: './tarjeta-digital.html',
  styleUrl: './tarjeta-digital.scss',
})
export class TarjetaDigital implements OnInit {
  readonly datos = input.required<TarjetaRevelada>();
  readonly cerrar = output<void>();

  protected readonly segundosRestantes = signal(SEGUNDOS_VISIBLE);
  protected readonly copiado = signal<'pan' | 'cvv' | null>(null);

  private readonly destroyRef = inject(DestroyRef);

  ngOnInit() {
    // Los datos solo viven en este signal, nunca en localStorage/sessionStorage. Se borran
    // solos a los 30s o al cerrar/navegar (el destroy limpia el intervalo en ambos casos).
    const id = setInterval(() => {
      const restante = this.segundosRestantes() - 1;
      this.segundosRestantes.set(restante);
      if (restante <= 0) this.cerrar.emit();
    }, 1000);
    this.destroyRef.onDestroy(() => clearInterval(id));
  }

  protected async copiar(valor: string, campo: 'pan' | 'cvv') {
    try {
      await navigator.clipboard.writeText(valor);
      this.copiado.set(campo);
      setTimeout(() => this.copiado.set(null), 1500);
    } catch {
      // ponytail: sin fallback manual de copiado; clipboard API ausente es un caso raro (sin TLS/permiso)
    }
  }
}
