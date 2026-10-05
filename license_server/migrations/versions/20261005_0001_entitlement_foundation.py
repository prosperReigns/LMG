"""add entitlement foundation

Revision ID: 20261005_0001
Revises: 59e7c4d5f192
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261005_0001"
down_revision = "59e7c4d5f192"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_code", sa.String(80), nullable=False),
        sa.Column("edition", sa.String(50), nullable=False, server_default="pro"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_devices", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("activation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("signed_package", sa.Text(), nullable=True),
        sa.Column("package_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("public_key_version", sa.String(30), nullable=False, server_default="v2"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legacy_license_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["legacy_license_id"], ["licenses.id"], ondelete="SET NULL"),
    )
    for name, cols in [
        ("ix_entitlements_customer_id", ["customer_id"]),
        ("ix_entitlements_school_id", ["school_id"]),
        ("ix_entitlements_product_code", ["product_code"]),
        ("ix_entitlements_status", ["status"]),
        ("ix_entitlements_expires_at", ["expires_at"]),
        ("ix_entitlements_legacy_license_id", ["legacy_license_id"]),
        ("ix_entitlements_product_edition_status", ["product_code", "edition", "status"]),
    ]:
        op.create_index(name, "entitlements", cols)

    op.create_table(
        "entitlement_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature_code", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("limits", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entitlement_id"], ["entitlements.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("entitlement_id", "feature_code", name="uq_entitlement_feature"),
    )
    op.create_index("ix_entitlement_features_entitlement_id", "entitlement_features", ["entitlement_id"])

    op.create_table(
        "entitlement_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entitlement_id"], ["entitlements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["license_devices.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entitlement_id", "device_id"),
    )
    op.create_index("ix_entitlement_devices_entitlement_id", "entitlement_devices", ["entitlement_id"])
    op.create_index("ix_entitlement_devices_device_id", "entitlement_devices", ["device_id"])

    op.create_table(
        "entitlement_renewals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("renewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plan_code", sa.String(50), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="NGN"),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("old_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entitlement_id"], ["entitlements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["renewed_by"], ["admins.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_entitlement_renewals_entitlement_id", "entitlement_renewals", ["entitlement_id"])
    op.create_index("ix_entitlement_renewals_payment_id", "entitlement_renewals", ["payment_id"])
    op.create_index("ix_entitlement_renewals_renewed_by", "entitlement_renewals", ["renewed_by"])

    op.add_column("purchase_sessions", sa.Column("edition", sa.String(50), nullable=True))
    op.add_column("purchase_sessions", sa.Column("installation_id", sa.String(255), nullable=True))
    op.add_column("purchase_sessions", sa.Column("machine_id", sa.String(255), nullable=True))
    op.add_column("purchase_sessions", sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_purchase_sessions_installation_id", "purchase_sessions", ["installation_id"])
    op.create_index("ix_purchase_sessions_machine_id", "purchase_sessions", ["machine_id"])
    op.create_index("ix_purchase_sessions_entitlement_id", "purchase_sessions", ["entitlement_id"])
    op.create_foreign_key(
        "fk_purchase_sessions_entitlement_id_entitlements",
        "purchase_sessions", "entitlements", ["entitlement_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("activation_tokens", sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_activation_tokens_entitlement_id", "activation_tokens", ["entitlement_id"])
    op.create_foreign_key(
        "fk_activation_tokens_entitlement_id_entitlements",
        "activation_tokens", "entitlements", ["entitlement_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("activations", sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("activations", sa.Column("installation_id", sa.String(255), nullable=True))
    op.add_column("activations", sa.Column("activation_type", sa.String(40), nullable=False, server_default="initial"))
    op.create_index("ix_activations_entitlement_id", "activations", ["entitlement_id"])
    op.create_index("ix_activations_installation_id", "activations", ["installation_id"])
    op.create_foreign_key(
        "fk_activations_entitlement_id_entitlements",
        "activations", "entitlements", ["entitlement_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("invoices", sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_invoices_entitlement_id", "invoices", ["entitlement_id"])
    op.create_foreign_key(
        "fk_invoices_entitlement_id_entitlements",
        "invoices", "entitlements", ["entitlement_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_entitlement_id_entitlements", "invoices", type_="foreignkey")
    op.drop_index("ix_invoices_entitlement_id", table_name="invoices")
    op.drop_column("invoices", "entitlement_id")

    op.drop_constraint("fk_activations_entitlement_id_entitlements", "activations", type_="foreignkey")
    op.drop_index("ix_activations_installation_id", table_name="activations")
    op.drop_index("ix_activations_entitlement_id", table_name="activations")
    op.drop_column("activations", "activation_type")
    op.drop_column("activations", "installation_id")
    op.drop_column("activations", "entitlement_id")

    op.drop_constraint("fk_activation_tokens_entitlement_id_entitlements", "activation_tokens", type_="foreignkey")
    op.drop_index("ix_activation_tokens_entitlement_id", table_name="activation_tokens")
    op.drop_column("activation_tokens", "entitlement_id")

    op.drop_constraint("fk_purchase_sessions_entitlement_id_entitlements", "purchase_sessions", type_="foreignkey")
    op.drop_index("ix_purchase_sessions_entitlement_id", table_name="purchase_sessions")
    op.drop_index("ix_purchase_sessions_machine_id", table_name="purchase_sessions")
    op.drop_index("ix_purchase_sessions_installation_id", table_name="purchase_sessions")
    op.drop_column("purchase_sessions", "entitlement_id")
    op.drop_column("purchase_sessions", "machine_id")
    op.drop_column("purchase_sessions", "installation_id")
    op.drop_column("purchase_sessions", "edition")

    op.drop_index("ix_entitlement_renewals_renewed_by", table_name="entitlement_renewals")
    op.drop_index("ix_entitlement_renewals_payment_id", table_name="entitlement_renewals")
    op.drop_index("ix_entitlement_renewals_entitlement_id", table_name="entitlement_renewals")
    op.drop_table("entitlement_renewals")

    op.drop_index("ix_entitlement_devices_device_id", table_name="entitlement_devices")
    op.drop_index("ix_entitlement_devices_entitlement_id", table_name="entitlement_devices")
    op.drop_table("entitlement_devices")

    op.drop_index("ix_entitlement_features_entitlement_id", table_name="entitlement_features")
    op.drop_table("entitlement_features")

    for name in [
        "ix_entitlements_product_edition_status",
        "ix_entitlements_legacy_license_id",
        "ix_entitlements_expires_at",
        "ix_entitlements_status",
        "ix_entitlements_product_code",
        "ix_entitlements_school_id",
        "ix_entitlements_customer_id",
    ]:
        op.drop_index(name, table_name="entitlements")
    op.drop_table("entitlements")
