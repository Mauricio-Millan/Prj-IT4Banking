import { ComponentFixture, TestBed } from '@angular/core/testing';

import { QuejaPage } from './queja-page';

describe('QuejaPage', () => {
  let component: QuejaPage;
  let fixture: ComponentFixture<QuejaPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QuejaPage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(QuejaPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
