"""allow entitlement-native devices and activations

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20261005_0002"
down_revision = "20261005_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "license_devices",
        "license_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.alter_column(
        "activation_tokens",
        "license_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.alter_column(
        "activations",
        "license_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # Existing rows must have legacy license ownership before reverting.
    bind = op.get_bind()
    for table in ("license_devices", "activation_tokens", "activations"):
        count = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE license_id IS NULL")
        ).scalar_one()
        if count:
            raise RuntimeError(
                f"Cannot downgrade: {table} contains {count} entitlement-native rows "
                "without a legacy license_id."
            )

    op.alter_column(
        "activations",
        "license_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "activation_tokens",
        "license_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "license_devices",
        "license_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
