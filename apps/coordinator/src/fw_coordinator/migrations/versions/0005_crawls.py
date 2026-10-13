"""Tenant-isolated durable crawl cycles and shared per-origin politeness."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = ("crawl_jobs", "crawl_frontier", "crawl_items")


def upgrade() -> None:
    schema = """
        CREATE SEQUENCE crawl_fence;
        CREATE TABLE crawl_jobs (
          tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE, id uuid NOT NULL,
          definition text NOT NULL, contract_hash text NOT NULL, contract jsonb NOT NULL,
          state text NOT NULL CHECK(state IN ('QUEUED','RUNNING','COMPLETE','FAILED','CANCELLED')),
          fence bigint, lease_until timestamptz, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          completed_at timestamptz, cancel_requested boolean NOT NULL DEFAULT false,
          pages integer NOT NULL DEFAULT 0, items integer NOT NULL DEFAULT 0, errors integer NOT NULL DEFAULT 0,
          added integer NOT NULL DEFAULT 0, changed integer NOT NULL DEFAULT 0, removed integer NOT NULL DEFAULT 0,
          alerts jsonb NOT NULL DEFAULT '[]', artifact text,
          PRIMARY KEY(tenant_id,id));
        CREATE INDEX crawl_jobs_pending ON crawl_jobs(tenant_id,created_at) WHERE state IN ('QUEUED','RUNNING');
        CREATE INDEX crawl_jobs_completed ON crawl_jobs(tenant_id,completed_at);
        CREATE TABLE crawl_frontier (
          tenant_id uuid NOT NULL, job_id uuid NOT NULL, path text NOT NULL,
          attempts integer NOT NULL DEFAULT 0, done boolean NOT NULL DEFAULT false,
          due_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(tenant_id,job_id,path), FOREIGN KEY(tenant_id,job_id) REFERENCES crawl_jobs(tenant_id,id) ON DELETE CASCADE);
        CREATE INDEX crawl_frontier_due ON crawl_frontier(tenant_id,job_id,due_at) WHERE NOT done;
        CREATE TABLE crawl_items (
          tenant_id uuid NOT NULL, definition text NOT NULL, identity text NOT NULL,
          content_hash text NOT NULL, data jsonb NOT NULL, seen_job uuid NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          PRIMARY KEY(tenant_id,definition,identity));
        CREATE INDEX crawl_items_retention ON crawl_items(tenant_id,updated_at);
        CREATE TABLE crawl_domains (origin_hash text PRIMARY KEY, next_at timestamptz NOT NULL);
        GRANT SELECT,INSERT,UPDATE,DELETE ON crawl_domains TO fw_app;
        GRANT USAGE ON SEQUENCE crawl_fence TO fw_app;
    """
    for statement in schema.split(";"):
        if statement.strip():
            op.execute(statement)
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid) "
            "WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)"
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO fw_app")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP TABLE crawl_domains")
    op.execute("DROP SEQUENCE crawl_fence")
