import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/** Raiz: solo delega al layout que resuelva el router. */
@Component({
  selector: 'bc-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
