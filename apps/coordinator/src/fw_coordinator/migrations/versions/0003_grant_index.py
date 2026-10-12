"""Keep grant digest uniqueness tenant-scoped, including databases that already ran 0002."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE workflow_grants DROP CONSTRAINT IF EXISTS workflow_grants_token_hash_key")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS workflow_grants_tenant_hash ON workflow_grants(tenant_id,token_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS workflow_grants_tenant_hash")
