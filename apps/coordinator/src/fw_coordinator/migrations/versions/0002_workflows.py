"""Durable general workflows, exact-action approvals and revocable MCP grants.

Additive migration: existing claims and freight consumers are preserved.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ("workflow_grants", "workflow_jobs", "workflow_approvals", "workflow_events")
SCHEMA = """
CREATE SEQUENCE workflow_fence;
CREATE TABLE workflow_grants (
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 id uuid NOT NULL, user_id uuid NOT NULL, token_hash text NOT NULL,
 scopes text[] NOT NULL, expires_at timestamptz NOT NULL, revoked_at timestamptz,
 PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id,token_hash), FOREIGN KEY (tenant_id,user_id) REFERENCES users(tenant_id,id)
);
CREATE TABLE workflow_jobs (
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 id uuid NOT NULL, grant_id uuid NOT NULL, identity text NOT NULL,
 workflow text NOT NULL, contract_hash text NOT NULL, action_hash text NOT NULL,
 account_id uuid NOT NULL, inputs jsonb NOT NULL,
 state text NOT NULL CHECK (state IN ('PENDING','QUEUED','LEASED','ACTING','CONFIRMED','FAILED','UNKNOWN','CANCELLED')),
 fence bigint, worker_id text, lease_expires_at timestamptz,
 cancel_requested boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,identity),
 FOREIGN KEY (tenant_id,grant_id) REFERENCES workflow_grants(tenant_id,id),
 FOREIGN KEY (tenant_id,account_id) REFERENCES accounts(tenant_id,id)
);
CREATE UNIQUE INDEX workflow_one_active_account ON workflow_jobs(tenant_id,account_id) WHERE state IN ('LEASED','ACTING');
CREATE INDEX workflow_pending ON workflow_jobs(tenant_id,state,created_at);
CREATE TABLE workflow_approvals (
 tenant_id uuid NOT NULL, job_id uuid NOT NULL, action_hash text NOT NULL,
 approver_id uuid NOT NULL, expires_at timestamptz NOT NULL, consumed_at timestamptz, revoked_at timestamptz,
 PRIMARY KEY (tenant_id,job_id),
 FOREIGN KEY (tenant_id,job_id) REFERENCES workflow_jobs(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY (tenant_id,approver_id) REFERENCES users(tenant_id,id)
);
CREATE TABLE workflow_events (
 tenant_id uuid NOT NULL, id bigserial, job_id uuid NOT NULL,
 at timestamptz NOT NULL DEFAULT clock_timestamp(), kind text NOT NULL, evidence jsonb NOT NULL,
 PRIMARY KEY (tenant_id,id), FOREIGN KEY (tenant_id,job_id) REFERENCES workflow_jobs(tenant_id,id) ON DELETE CASCADE
);
CREATE INDEX workflow_timeline ON workflow_events(tenant_id,job_id,id);
"""


def upgrade() -> None:
    for statement in SCHEMA.split(";"):
        if statement.strip():
            op.execute(statement)
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id',true),'')::uuid) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id',true),'')::uuid)"
        )
    op.execute("GRANT SELECT, INSERT, UPDATE ON workflow_grants, workflow_jobs, workflow_approvals TO fw_app")
    op.execute("GRANT SELECT, INSERT ON workflow_events TO fw_app")
    op.execute("GRANT USAGE ON SEQUENCE workflow_fence, workflow_events_id_seq TO fw_app")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP SEQUENCE workflow_fence")
