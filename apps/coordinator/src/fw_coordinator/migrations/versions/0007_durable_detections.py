"""Keep raw detections durable until their dispatch decision commits, including across moves."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE outbox ADD COLUMN consumed_at timestamptz")
    op.execute("ALTER TABLE outbox ADD COLUMN detection_key text")
    op.execute(
        "CREATE UNIQUE INDEX outbox_detection_identity ON outbox(tenant_id,detection_key) WHERE topic='detection.dispatch'"
    )
    op.execute(
        "CREATE INDEX outbox_detection_pending ON outbox(tenant_id,published_at,id) "
        "WHERE topic='detection.dispatch' AND consumed_at IS NULL"
    )
    op.execute("GRANT SELECT,INSERT ON outbox TO fw_worker")
    op.execute("GRANT USAGE ON SEQUENCE outbox_id_seq TO fw_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT,INSERT ON outbox FROM fw_worker")
    op.execute("REVOKE USAGE ON SEQUENCE outbox_id_seq FROM fw_worker")
    op.execute("DROP INDEX outbox_detection_pending")
    op.execute("DROP INDEX outbox_detection_identity")
    op.execute("ALTER TABLE outbox DROP COLUMN detection_key")
    op.execute("ALTER TABLE outbox DROP COLUMN consumed_at")
