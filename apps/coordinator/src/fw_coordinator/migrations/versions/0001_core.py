"""Coordination core: tenants, cells, accounts, session vault, filters, schedules, claims, workers,
audit log and outbox. Every tenant table has tenant_id, Row-Level Security (FORCED, so even the
owner role is filtered) and indexes that start with tenant_id.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "users",
    "accounts",
    "account_sessions",
    "filters",
    "schedules",
    "target_jobs",
    "claims",
    "claim_events",
    "workers",
    "audit_log",
    "outbox",
]

SCHEMA = """
-- ---------- directory tables (not tenant data; no RLS) ----------
CREATE TABLE tenants (
  id          uuid PRIMARY KEY,
  slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,40}$'),
  name        text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- A cell = one Redis + its watchers, dispatcher and worker pool. Endpoints live in configuration.
CREATE TABLE cells (
  id          text PRIMARY KEY CHECK (id ~ '^[a-z0-9-]{1,40}$'),
  name        text NOT NULL,
  region      text NOT NULL,
  capacity    int  NOT NULL CHECK (capacity > 0),
  enabled     boolean NOT NULL DEFAULT true
);

-- Which cell runs which tenant. version increases on every move (workers watch it).
CREATE TABLE tenant_cells (
  tenant_id   uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  cell_id     text NOT NULL REFERENCES cells(id),
  version     int  NOT NULL DEFAULT 1,
  moved_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX tenant_cells_cell ON tenant_cells (cell_id);

-- Login needs the tenant before the tenant is known: this maps an email to its tenant only.
CREATE TABLE user_directory (
  email       text PRIMARY KEY CHECK (email = lower(email)),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL
);

-- ---------- tenant tables ----------
CREATE TABLE users (
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id             uuid NOT NULL,
  email          text NOT NULL CHECK (email = lower(email)),
  name           text NOT NULL,
  role           text NOT NULL CHECK (role IN ('owner', 'operator', 'viewer', 'demo')),
  password_hash  text NOT NULL,
  totp_key_id    text,
  totp_wrapped   bytea,
  totp_nonce     bytea,
  totp_sealed    bytea,
  mfa_enabled    boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_seen_at   timestamptz,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, email)
);

-- Target-site logins the fleet uses. The password is envelope-encrypted (fw_core.crypto).
CREATE TABLE accounts (
  tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id                  uuid NOT NULL,
  label               text NOT NULL,
  target              text NOT NULL,
  username            text NOT NULL,
  email               text NOT NULL,
  account_group       text NOT NULL DEFAULT 'default',
  otp_channel         text NOT NULL DEFAULT 'email' CHECK (otp_channel IN ('email', 'sms', 'manual')),
  rate_limit_per_min  int  NOT NULL DEFAULT 120 CHECK (rate_limit_per_min > 0),
  enabled             boolean NOT NULL DEFAULT true,
  cred_key_id         text NOT NULL,
  cred_wrapped        bytea NOT NULL,
  cred_nonce          bytea NOT NULL,
  cred_sealed         bytea NOT NULL,
  -- Account mutex at the worker level: one worker slot holds an account at a time.
  holder_worker       text,
  holder_expires_at   timestamptz,
  created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, target, username)
);
CREATE INDEX accounts_free ON accounts (tenant_id, holder_expires_at) WHERE enabled;

-- Session vault: Playwright storage_state, envelope-encrypted, one row per account.
CREATE TABLE account_sessions (
  tenant_id          uuid NOT NULL,
  account_id         uuid NOT NULL,
  key_id             text NOT NULL,
  wrapped            bytea NOT NULL,
  nonce              bytea NOT NULL,
  sealed             bytea NOT NULL,
  state              text NOT NULL CHECK (state IN ('fresh', 'expiring', 'expired', 'otp_required')),
  expires_at         timestamptz,
  ttl_s              int,
  refreshed_at       timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id, account_id),
  FOREIGN KEY (tenant_id, account_id) REFERENCES accounts (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE filters (
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id             uuid NOT NULL,
  name           text NOT NULL,
  enabled        boolean NOT NULL DEFAULT true,
  origin         text NOT NULL DEFAULT 'Any',
  destination    text NOT NULL DEFAULT 'Any',
  min_rate_usd   int  NOT NULL DEFAULT 0 CHECK (min_rate_usd >= 0),
  equipment      text[] NOT NULL DEFAULT '{}',
  max_weight_lb  int  NOT NULL DEFAULT 80000 CHECK (max_weight_lb > 0),
  account_group  text NOT NULL DEFAULT 'default',
  version        int  NOT NULL DEFAULT 1,
  updated_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, name)
);

CREATE TABLE schedules (
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id          uuid NOT NULL,
  name        text NOT NULL,
  timezone    text NOT NULL,
  windows     jsonb NOT NULL DEFAULT '[]',
  targets     uuid[] NOT NULL DEFAULT '{}',
  enabled     boolean NOT NULL DEFAULT true,
  updated_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, name)
);

-- A job on the target that matched a filter.
CREATE TABLE target_jobs (
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key           text NOT NULL,
  published_at  timestamptz,
  first_seen_at timestamptz NOT NULL,
  payload       jsonb NOT NULL,
  PRIMARY KEY (tenant_id, key)
);

CREATE SEQUENCE claim_fence;

-- One claim per job per tenant: the unique key is the database-enforced "exactly one winner".
CREATE TABLE claims (
  tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id                uuid NOT NULL,
  target_job_key    text NOT NULL,
  state             text NOT NULL CHECK (state IN ('DETECTED', 'QUEUED', 'LEASED', 'ACTING',
                                                 'CONFIRMED', 'FAILED', 'UNKNOWN', 'RECONCILED')),
  filter_id         uuid,
  cell_id           text NOT NULL,
  lane              text NOT NULL,
  rate_usd          int  NOT NULL,
  account_id        uuid,
  worker_id         text,
  fence             bigint,
  lease_expires_at  timestamptz,
  published_at      timestamptz,
  seen_at           timestamptz NOT NULL,
  clock_offset_ms   double precision,
  queued_at         timestamptz NOT NULL DEFAULT clock_timestamp(),
  leased_at         timestamptz,
  act_sent_at       timestamptz,
  confirmed_at      timestamptz,
  finished_at       timestamptz,
  result            text,
  resolution        text,
  dispatches        int NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, id),
  UNIQUE (tenant_id, target_job_key)
);
-- Account mutex at the claim level: at most one active lease per target account.
CREATE UNIQUE INDEX claims_one_active_per_account ON claims (tenant_id, account_id) WHERE state IN ('LEASED', 'ACTING');
CREATE INDEX claims_recent ON claims (tenant_id, queued_at DESC, id DESC);
CREATE INDEX claims_open ON claims (tenant_id, state, lease_expires_at) WHERE state IN ('QUEUED', 'LEASED', 'ACTING', 'UNKNOWN');

-- Append-only history of every claim transition.
CREATE TABLE claim_events (
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id         bigserial,
  claim_id   uuid NOT NULL,
  at         timestamptz NOT NULL DEFAULT clock_timestamp(),
  state      text NOT NULL,
  actor      text NOT NULL,
  note       text,
  PRIMARY KEY (tenant_id, id)
);
CREATE INDEX claim_events_claim ON claim_events (tenant_id, claim_id, id);

-- One row per worker slot (one browser context with a role).
CREATE TABLE workers (
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id            text NOT NULL,
  process_id    text NOT NULL,
  cell_id       text NOT NULL,
  mode          text NOT NULL CHECK (mode IN ('watcher', 'claimer', 'crawler')),
  account_id    uuid,
  state         text NOT NULL DEFAULT 'running' CHECK (state IN ('starting', 'running', 'draining', 'stopped')),
  version       text NOT NULL,
  memory_mb     int,
  cpu_pct       real,
  clock_offset_ms double precision,
  started_at    timestamptz NOT NULL DEFAULT clock_timestamp(),
  heartbeat_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id, id)
);
CREATE INDEX workers_heartbeat ON workers (tenant_id, heartbeat_at DESC);

-- Append-only audit log of every mutation.
CREATE TABLE audit_log (
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id         bigserial,
  at         timestamptz NOT NULL DEFAULT clock_timestamp(),
  actor      text NOT NULL,
  role       text NOT NULL,
  action     text NOT NULL,
  target     text NOT NULL,
  detail     text NOT NULL,
  ip_prefix  text,
  PRIMARY KEY (tenant_id, id)
);
CREATE INDEX audit_recent ON audit_log (tenant_id, at DESC, id DESC);

-- Transactional outbox: written in the same transaction as the state change it announces.
CREATE TABLE outbox (
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  id            bigserial,
  created_at    timestamptz NOT NULL DEFAULT clock_timestamp(),
  topic         text NOT NULL,
  payload       jsonb NOT NULL,
  published_at  timestamptz,
  PRIMARY KEY (tenant_id, id)
);
CREATE INDEX outbox_pending ON outbox (tenant_id, id) WHERE published_at IS NULL;
"""

GRANTS = """
GRANT SELECT ON tenants, cells, tenant_cells TO fw_app, fw_worker;
GRANT INSERT, UPDATE ON tenants, cells, tenant_cells TO fw_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_directory TO fw_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON users, accounts, account_sessions, filters, schedules, target_jobs, claims, workers TO fw_app;
GRANT SELECT, INSERT ON claim_events, audit_log TO fw_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON outbox TO fw_app;
GRANT USAGE ON SEQUENCE claim_fence, claim_events_id_seq, audit_log_id_seq, outbox_id_seq TO fw_app;

-- Workers: read what they need, change only their own operational columns.
GRANT SELECT ON accounts, account_sessions, filters, claims, workers TO fw_worker;
GRANT UPDATE (holder_worker, holder_expires_at) ON accounts TO fw_worker;
GRANT INSERT, UPDATE ON account_sessions TO fw_worker;
GRANT UPDATE (state, worker_id, account_id, fence, lease_expires_at, leased_at, act_sent_at, confirmed_at, finished_at, result, resolution)
  ON claims TO fw_worker;
GRANT INSERT ON claim_events TO fw_worker;
GRANT INSERT, UPDATE, DELETE ON workers TO fw_worker;
GRANT USAGE ON SEQUENCE claim_fence, claim_events_id_seq TO fw_worker;
"""


def _statements(sql: str) -> list[str]:
    """asyncpg runs one statement per call. Comment lines go first (they may contain ";")."""
    code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [part.strip() for part in code.split(";") if part.strip()]


def upgrade() -> None:
    for statement in _statements(SCHEMA):
        op.execute(statement)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )
    for statement in _statements(GRANTS):
        op.execute(statement)


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP SEQUENCE IF EXISTS claim_fence")
    for table in ("user_directory", "tenant_cells", "cells", "tenants"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
