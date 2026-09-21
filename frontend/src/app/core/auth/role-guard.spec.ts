import { TestBed } from '@angular/core/testing';

import { roleGuard } from './role-guard';

describe('roleGuard', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({});
  });

  it('should be created', () => {
    const executeGuard = () => TestBed.runInInjectionContext(() => roleGuard(['analista'])({} as any, [] as any));
    expect(executeGuard).toBeTruthy();
  });
});
