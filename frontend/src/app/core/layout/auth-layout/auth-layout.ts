import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/** Shell publico: login y onboarding. Sin navegacion, contenido centrado. */
@Component({
  selector: 'bc-auth-layout',
  imports: [RouterOutlet],
  templateUrl: './auth-layout.html',
  styleUrl: './auth-layout.scss',
})
export class AuthLayout {}
