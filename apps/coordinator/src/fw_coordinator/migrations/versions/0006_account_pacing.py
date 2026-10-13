"""One DB-clock account admission budget shared by workflow and freight execution."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE accounts ADD COLUMN next_action_at timestamptz")
    op.execute("GRANT UPDATE(next_action_at) ON accounts TO fw_worker")


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN next_action_at")
