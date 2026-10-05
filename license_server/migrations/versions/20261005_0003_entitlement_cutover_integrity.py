"""add entitlement cutover integrity constraints

Revision ID: 20261005_0003
Revises: 20261005_0002
Create Date: 2026-10-05
"""

from alembic import op


revision = "20261005_0003"
down_revision = "20261005_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One legacy License can map to only one canonical Entitlement.
    # The partial index permits native entitlements with no legacy license.
    op.create_index(
        "uq_entitlements_legacy_license_id",
        "entitlements",
        ["legacy_license_id"],
        unique=True,
        postgresql_where="legacy_license_id IS NOT NULL",
    )

    # A machine may have at most one active activation for an entitlement.
    op.create_index(
        "uq_active_entitlement_activation_machine",
        "activations",
        ["entitlement_id", "machine_id"],
        unique=True,
        postgresql_where="entitlement_id IS NOT NULL AND status = 'active'",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_active_entitlement_activation_machine",
        table_name="activations",
    )
    op.drop_index(
        "uq_entitlements_legacy_license_id",
        table_name="entitlements",
    )
