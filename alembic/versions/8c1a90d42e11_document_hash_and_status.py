"""Add document content deduplication and processing status.

Revision ID: 8c1a90d42e11
Revises: fef053c273c6
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "8c1a90d42e11"
down_revision: str | Sequence[str] | None = "fef053c273c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("status", sa.String(length=24), server_default="ready", nullable=False),
    )
    op.create_unique_constraint(
        "uq_documents_content_hash", "documents", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_content_hash", "documents", type_="unique")
    op.drop_column("documents", "status")
    op.drop_column("documents", "content_hash")
