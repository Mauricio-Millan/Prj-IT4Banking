import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

interface Diferenciador {
  titulo: string;
  detalle: string;
}

interface Herramienta {
  nombre: string;
  detalle: string;
}

/**
 * V1: pagina 100% estatica, cero llamadas a la API — debe renderizar con el backend apagado.
 * V7: no se monta en AuthLayout ni ClientLayout, es autocontenida con su propio header/footer.
 */
@Component({
  selector: 'bc-landing-page',
  imports: [RouterLink],
  templateUrl: './landing-page.html',
  styleUrl: './landing-page.scss',
})
export class LandingPage {
  protected readonly diferenciadores: Diferenciador[] = [
    { titulo: 'Apertura en minutos', detalle: 'Regístrate desde el celular o la web, sin ir a una oficina ni hacer cola.' },
    { titulo: 'Tarjeta virtual inmediata', detalle: 'Tu tarjeta de débito queda lista para usar apenas terminas de registrarte.' },
    { titulo: 'Sin comisiones de mantenimiento', detalle: 'Tu cuenta de ahorro no cobra membresía ni cargos por mantenerla abierta.' },
    { titulo: 'Transferencias en segundos', detalle: 'Envía dinero a otra cuenta del banco al instante, cuando lo necesites.' },
  ];

  protected readonly herramientas: Herramienta[] = [
    { nombre: 'Cuenta de ahorro', detalle: 'Deposita, retira y controla tu saldo en tiempo real.' },
    { nombre: 'Tarjeta de débito virtual', detalle: 'Se emite sola al abrir tu cuenta, sin trámites adicionales.' },
    { nombre: 'Transferencias', detalle: 'Entre tus cuentas o hacia otra persona del banco.' },
    { nombre: 'Préstamos de consumo', detalle: 'Solicita un préstamo simple y conoce la decisión al instante.' },
    { nombre: 'Atención de reclamos', detalle: 'Registra una queja y sigue su estado desde tu banca.' },
  ];
}
