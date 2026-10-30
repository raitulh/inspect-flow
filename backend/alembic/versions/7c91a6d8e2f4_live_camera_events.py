"""Allow camera-originated events without uploaded video or analysis job.

Revision ID: 7c91a6d8e2f4
Revises: e0d2cc7db578
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "7c91a6d8e2f4"
down_revision = "e0d2cc7db578"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("detection_events") as batch_op:
        batch_op.alter_column("video_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.alter_column("job_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    # Cannot safely restore NOT NULL while live-camera events still exist.
    op.execute("DELETE FROM detection_events WHERE video_id IS NULL OR job_id IS NULL")
    with op.batch_alter_table("detection_events") as batch_op:
        batch_op.alter_column("video_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column("job_id", existing_type=sa.String(length=36), nullable=False)
