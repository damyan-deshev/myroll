I am still running the Slice 13 implementation pass.

Rough progress: 92% complete.

Done:
- storage/export/restore backend;
- demo reset/start scripts;
- original public demo seed;
- generated demo asset pack;
- ignored local demo override template;
- Storage / Demo widget;
- backend tests green;
- frontend tests green;
- frontend build green;
- standalone demo Playwright export/restore test passed once.

Currently fixing the full Playwright suite against the seeded demo profile:
- demo spec had widget overlap during Export click;
- party tracker spec assumed no existing seeded campaign and is being hardened to select its own campaign explicitly.

Remaining:
- rerun full Playwright suite;
- stop local demo server;
- final summary.
