import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { QuejasRevisionPage } from './quejas-revision-page';

describe('QuejasRevisionPage', () => {
  let component: QuejasRevisionPage;
  let fixture: ComponentFixture<QuejasRevisionPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QuejasRevisionPage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    })
    .compileComponents();

    fixture = TestBed.createComponent(QuejasRevisionPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
