"""Persist uploaded episode sources and AI scene-analysis results."""
from alembic import op
import sqlalchemy as sa

revision = "0002_video_sources"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "source_videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drama_id", sa.Integer(), sa.ForeignKey("dramas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UPLOADED"),
        sa.Column("analysis_result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analysis_authorized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_videos_drama_id", "source_videos", ["drama_id"])

def downgrade() -> None:
    op.drop_index("ix_source_videos_drama_id", table_name="source_videos")
    op.drop_table("source_videos")
