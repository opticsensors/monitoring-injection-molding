-- Test stack only. Never apply these passwords to production.
ALTER ROLE monitoring_ingest PASSWORD 'test-only-ingest';
ALTER ROLE monitoring_reader PASSWORD 'test-only-reader';
