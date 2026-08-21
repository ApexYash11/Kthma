# SQLite + SQLAlchemy for persistence

AGENTS.md listed PostgreSQL / Supabase. For a solo hackathon that is extra ops. Recovery cases, audit trail, and eval results live in a local SQLite file accessed through SQLAlchemy so a Postgres dialect swap stays possible.

No Supabase until we have a reason beyond "the spec mentioned it".

**Status:** accepted
