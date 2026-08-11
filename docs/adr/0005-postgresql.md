# ADR 0005: PostgreSQL persistence

Status: accepted — 2026-08-11

PostgreSQL is selected for transactional device and maintenance workflows,
unique constraints for ingestion idempotency, time-range indexes, JSON metadata
where schemas evolve, and repeatable Alembic migrations. SQLite is restricted
to fast unit tests because concurrency, timestamp, and constraint behavior can
differ. Integration and migration evidence must use PostgreSQL.

