import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter, RouterLink } from '@angular/router';
import { LandingPage } from './landing-page';

describe('LandingPage', () => {
  let fixture: ComponentFixture<LandingPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LandingPage],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(LandingPage);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('tiene exactamente un h1', () => {
    expect(fixture.nativeElement.querySelectorAll('h1').length).toBe(1);
  });

  it('los CTA apuntan a /login y /registro', () => {
    const hrefs = fixture.debugElement
      .queryAll(By.directive(RouterLink))
      .map(el => el.injector.get(RouterLink).href);
    expect(hrefs).toContain('/login');
    expect(hrefs).toContain('/registro');
  });
});
