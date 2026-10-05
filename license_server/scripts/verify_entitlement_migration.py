"""Examcenter entitlement migration preflight and cutover verification.

Run from the license_server directory:

    python scripts/verify_entitlement_migration.py --check

To apply Alembic migrations and then migrate legacy licenses:

    python scripts/verify_entitlement_migration.py --migrate

The migration flag is intentionally explicit so a normal health check can never
change the production database.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import func, inspect, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from app.database.session import SessionLocal, engine
from app.models.activation import Activation
from app.models.activation_token import ActivationToken
from app.models.entitlement import Entitlement
from app.models.entitlement_device import EntitlementDevice
from app.models.entitlement_feature import EntitlementFeature
from app.models.entitlement_renewal import EntitlementRenewal
from app.models.license import License
from app.services.entitlement_migration_service import EntitlementMigrationService


REQUIRED_TABLES = {
    "entitlements",
    "entitlement_features",
    "entitlement_devices",
    "entitlement_renewals",
}

REQUIRED_NULLABLE_COLUMNS = {
    "license_devices": {"license_id"},
    "activation_tokens": {"license_id"},
    "activations": {"license_id"},
}


def check_schema() -> dict:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_tables = sorted(REQUIRED_TABLES - tables)

    nullable_errors: list[str] = []
    for table, columns in REQUIRED_NULLABLE_COLUMNS.items():
        if table not in tables:
            nullable_errors.append(f"{table}: table missing")
            continue
        actual = {
            column["name"]: column["nullable"]
            for column in inspector.get_columns(table)
        }
        for column in columns:
            if column not in actual:
                nullable_errors.append(f"{table}.{column}: column missing")
            elif not actual[column]:
                nullable_errors.append(f"{table}.{column}: must be nullable")

    with engine.connect() as conn:
        revision = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()

    return {
        "alembic_revision": revision,
        "missing_tables": missing_tables,
        "nullable_errors": nullable_errors,
        "schema_ok": not missing_tables and not nullable_errors,
    }


def report_data() -> dict:
    with SessionLocal() as db:
        licenses = db.scalar(select(func.count()).select_from(License.__table__))
        entitlements = db.scalar(select(func.count()).select_from(Entitlement.__table__))
        migrated = db.scalar(
            select(func.count())
            .select_from(Entitlement.__table__)
            .where(Entitlement.legacy_license_id.is_not(None))
        )
        entitlement_devices = db.scalar(
            select(func.count()).select_from(EntitlementDevice.__table__)
        )
        features = db.scalar(
            select(func.count()).select_from(EntitlementFeature.__table__)
        )
        renewals = db.scalar(
            select(func.count()).select_from(EntitlementRenewal.__table__)
        )
        entitlement_tokens = db.scalar(
            select(func.count())
            .select_from(ActivationToken.__table__)
            .where(ActivationToken.entitlement_id.is_not(None))
        )
        entitlement_activations = db.scalar(
            select(func.count())
            .select_from(Activation.__table__)
            .where(Activation.entitlement_id.is_not(None))
        )

    return {
        "licenses": licenses,
        "entitlements": entitlements,
        "legacy_license_entitlements": migrated,
        "entitlement_devices": entitlement_devices,
        "entitlement_features": features,
        "entitlement_renewals": renewals,
        "entitlement_activation_tokens": entitlement_tokens,
        "entitlement_activations": entitlement_activations,
    }


def migrate() -> dict:
    alembic_ini = ROOT / "alembic.ini"
    config = Config(str(alembic_ini))
    command.upgrade(config, "head")

    schema = check_schema()
    if not schema["schema_ok"]:
        raise RuntimeError(f"Schema verification failed: {schema}")

    with SessionLocal() as db:
        result = EntitlementMigrationService(db).migrate_all()

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Inspect the current database without changing it.",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Apply migrations and migrate existing licenses.",
    )
    args = parser.parse_args()

    if args.check == args.migrate:
        parser.error("Choose exactly one of --check or --migrate")

    if not os.getenv("DATABASE_URL"):
        print("WARNING: DATABASE_URL is not set; app settings may use another configured source.")

    if args.migrate:
        print("Applying Alembic migrations and migrating legacy licenses...")
        result = migrate()
        print(f"Legacy migration result: {result}")

    schema = check_schema()
    print(f"Schema OK: {schema['schema_ok']}")
    print(f"Alembic revision: {schema['alembic_revision']}")
    if schema["missing_tables"]:
        print(f"Missing tables: {schema['missing_tables']}")
    if schema["nullable_errors"]:
        print(f"Nullable-column errors: {schema['nullable_errors']}")

    print(f"Data: {report_data()}")
    return 0 if schema["schema_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
