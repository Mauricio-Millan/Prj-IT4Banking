import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BackofficeLayout } from './backoffice-layout';

describe('BackofficeLayout', () => {
  let component: BackofficeLayout;
  let fixture: ComponentFixture<BackofficeLayout>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BackofficeLayout]
    })
    .compileComponents();

    fixture = TestBed.createComponent(BackofficeLayout);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
