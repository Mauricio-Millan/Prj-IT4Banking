import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PrestamosPage } from './prestamos-page';

describe('PrestamosPage', () => {
  let component: PrestamosPage;
  let fixture: ComponentFixture<PrestamosPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PrestamosPage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PrestamosPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
