"""Durable fair rotation of inconclusive reconciliation attempts."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE workflow_jobs ADD COLUMN last_reconciled_at timestamptz")
    op.execute(
        "CREATE INDEX workflow_reconcile_rotation ON workflow_jobs(tenant_id,last_reconciled_at,created_at) WHERE state='UNKNOWN'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX workflow_reconcile_rotation")
    op.execute("ALTER TABLE workflow_jobs DROP COLUMN last_reconciled_at")
