import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TarjetasPage } from './tarjetas-page';

describe('TarjetasPage', () => {
  let component: TarjetasPage;
  let fixture: ComponentFixture<TarjetasPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TarjetasPage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(TarjetasPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
