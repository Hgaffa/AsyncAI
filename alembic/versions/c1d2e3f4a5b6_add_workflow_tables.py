"""Add workflow tables and job workflow columns

Revision ID: c1d2e3f4a5b6
Revises: b971cc333cde
Create Date: 2026-03-10 00:09:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b971cc333cde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create workflows table (workflow_status enum created automatically)
    op.create_table(
        "workflows",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="workflow_status"),
            nullable=False,
        ),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 2. Create workflow_steps table (step_status enum created automatically)
    op.create_table(
        "workflow_steps",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="step_status"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 3. Create task_results table
    op.create_table(
        "task_results",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", postgresql.JSONB(), nullable=True),
    )

    # 4. Add workflow_id and step_name to the job table
    op.add_column("job", sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=True))
    op.add_column("job", sa.Column("step_name", sa.String(255), nullable=True))

    # 5. Add FK constraint from job.workflow_id -> workflows.id
    op.create_foreign_key(
        "fk_job_workflow_id",
        "job",
        "workflows",
        ["workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Reverse in order: FK first, then columns, then tables, then enum types
    op.drop_constraint("fk_job_workflow_id", "job", type_="foreignkey")
    op.drop_column("job", "step_name")
    op.drop_column("job", "workflow_id")
    op.drop_table("task_results")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
    op.execute("DROP TYPE IF EXISTS step_status")
    op.execute("DROP TYPE IF EXISTS workflow_status")
