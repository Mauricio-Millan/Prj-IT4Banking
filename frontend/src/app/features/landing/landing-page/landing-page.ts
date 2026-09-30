import { CurrencyPipe } from '@angular/common';
import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface Diferenciador {
  titulo: string;
  detalle: string;
}

interface Herramienta {
  nombre: string;
  detalle: string;
}

interface SegmentoPrestamo {
  id: string;
  etiqueta: string;
  limite: number;
  tasa: number;
}

interface Testimonio {
  nombre: string;
  rol: string;
  iniciales: string;
  texto: string;
}

// Mismo limite de autoevaluacion y tasa (TEA) que services/prestamos.py::LIMITES_SEGMENTO.
// Duplicado deliberado: esta pagina no llama a la API (V1, cero llamadas al backend), asi que
// no puede leerlas de ahi. Si cambian en el backend, actualizar tambien aqui.
const SEGMENTOS_PRESTAMO: SegmentoPrestamo[] = [
  { id: 'joven', etiqueta: 'Joven', limite: 5000, tasa: 22.0 },
  { id: 'clasico', etiqueta: 'Clásico', limite: 15000, tasa: 18.5 },
  { id: 'premium', etiqueta: 'Premium', limite: 50000, tasa: 14.9 },
  { id: 'empresa', etiqueta: 'Empresa', limite: 100000, tasa: 16.0 },
];

const PLAZOS = [12, 18, 24, 36, 48];

/**
 * V1: pagina 100% estatica, cero llamadas a la API — debe renderizar con el backend apagado.
 * V7: no se monta en AuthLayout ni ClientLayout, es autocontenida con su propio header/footer.
 *
 * Estadísticas ("+250K clientes") y testimonios son contenido de ejemplo para la demo del curso
 * (aprobado explícitamente: se explica en la presentación que es un prototipo). El simulador de
 * préstamos, en cambio, usa las tasas y límites reales por segmento — nunca una tasa inventada.
 */
@Component({
  selector: 'bc-landing-page',
  imports: [RouterLink, FormsModule, CurrencyPipe],
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

  protected readonly estadisticas: [string, string][] = [
    ['+250K', 'Clientes digitales'],
    ['24/7', 'Atención digital'],
    ['100%', 'Operaciones online'],
    ['0', 'Comisiones ocultas'],
  ];

  protected readonly testimonios: Testimonio[] = [
    { nombre: 'María Torres', rol: 'Cliente BancoCloud', iniciales: 'MT', texto: 'Abrí mi cuenta en minutos y la experiencia desde el celular ha sido excelente.' },
    { nombre: 'Carlos Mendoza', rol: 'Cliente BancoCloud', iniciales: 'CM', texto: 'La tarjeta es práctica y el control de mis gastos desde la app me facilita todo.' },
    { nombre: 'Ana Rodríguez', rol: 'Cliente BancoCloud', iniciales: 'AR', texto: 'Pude simular mi préstamo y entender exactamente cuánto iba a pagar.' },
  ];

  protected readonly segmentos = SEGMENTOS_PRESTAMO;
  protected readonly plazos = PLAZOS;

  protected readonly segmentoId = signal(SEGMENTOS_PRESTAMO[0].id);
  protected readonly monto = signal(3000);
  protected readonly plazo = signal(24);

  protected readonly segmento = computed(
    () => this.segmentos.find(s => s.id === this.segmentoId()) ?? this.segmentos[0],
  );

  // Sistema frances (cuota fija), misma formula que generar_cronograma en services/prestamos.py:
  // TEM derivada de la TEA real del segmento -- solo cambia la precision (float aqui basta,
  // es un estimado de marketing, no una transaccion real que exija Decimal).
  protected readonly cuotaMensual = computed(() => {
    const tem = Math.pow(1 + this.segmento().tasa / 100, 1 / 12) - 1;
    const n = this.plazo();
    if (tem === 0) return this.monto() / n;
    return (this.monto() * tem) / (1 - Math.pow(1 + tem, -n));
  });

  protected cambiarSegmento(id: string): void {
    this.segmentoId.set(id);
    const limite = this.segmentos.find(s => s.id === id)?.limite ?? this.monto();
    if (this.monto() > limite) this.monto.set(limite);
  }
}
