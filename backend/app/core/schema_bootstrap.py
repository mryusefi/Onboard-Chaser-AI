"""Dev-mode additive schema reconciliation (companion to create_all).

Background (root cause of the create-onboarding / dashboard 500s):
``Base.metadata.create_all()`` creates NEW tables but never ALTERs existing
ones. The local Postgres volume was created during the early user stories, so
columns introduced later (US07 invitation_*, US08 reminder_logs, US09
reminder_configs, US11 verification_*) were missing from old tables — every
SELECT referencing them raised UndefinedColumn -> HTTP 500.

``reconcile_additive_schema`` closes that gap for dev mode: it adds missing
columns declared in the model metadata (nullable, then backfills the column's
Python-side default for existing rows) and pre-creates native enum types on
Postgres before the ALTERs. It NEVER drops or changes existing columns, so it
is safe on every startup. Production should still move to Alembic (see
README section 6).
"""
import enum
import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _default_sql_value(column):
    """Scalar Python-side default suitable for a backfill UPDATE (or None)."""
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return None
    arg = default.arg
    # SQLAlchemy stores Enum members by NAME (e.g. 'NOT_SENT'), not value.
    if isinstance(arg, enum.Enum):
        return arg.name
    return arg


def reconcile_additive_schema(engine, base) -> list[str]:
    """
    Add model-declared columns missing from existing tables; backfill
    defaults. Returns a list of human-readable actions (for logging/tests).

    Idempotent: safe to call on every startup.
    """
    actions = []
    conn = engine.connect()
    try:
        insp = inspect(conn)
        existing_tables = set(insp.get_table_names())
        is_pg = engine.dialect.name == "postgresql"

        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # brand-new table: create_all already handled it
            known_cols = {c["name"] for c in insp.get_columns(table.name)}
            for column in table.columns:
                if column.name in known_cols:
                    continue
                col_sql = column.type.compile(dialect=engine.dialect)
                if is_pg:
                    # Native enum types must exist before the ALTER references
                    # them; checkfirst=True makes this a no-op when present.
                    # Only SAEnum has create() — guard the attribute so plain
                    # types (String, DateTime, …) are skipped cleanly.
                    if hasattr(column.type, "create"):
                        try:
                            column.type.create(bind=conn, checkfirst=True)
                        except SQLAlchemyError:
                            pass
                # Added nullable regardless of the model's nullability:
                # existing rows cannot satisfy NOT NULL, and the Python-side
                # default keeps new ORM writes correct. (Plain ADD COLUMN —
                # the known_cols check above already guarantees absence, and
                # IF NOT EXISTS isn't valid SQLite for the test path.)
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" '
                         f'ADD COLUMN "{column.name}" {col_sql}')
                )
                default_value = _default_sql_value(column)
                if default_value is not None:
                    conn.execute(
                        text(f'UPDATE "{table.name}" '
                             f'SET "{column.name}" = :v '
                             f'WHERE "{column.name}" IS NULL'),
                        {"v": default_value},
                    )
                actions.append(f"{table.name}.{column.name}")
        conn.commit()
    finally:
        conn.close()
    if actions:
        logger.warning(
            "Reconciled schema drift — added missing columns (create_all does "
            "not ALTER existing tables): %s", ", ".join(actions),
        )
    return actions
