import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CuentasPage } from './cuentas-page';

describe('CuentasPage', () => {
  let component: CuentasPage;
  let fixture: ComponentFixture<CuentasPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CuentasPage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CuentasPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
