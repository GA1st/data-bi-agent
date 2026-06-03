"""
Lightweight database migration runner.
Applies SQL files from migrations/ in version order.
Tracks applied migrations in schema_version table.
"""
from pathlib import Path

from core.database import execute_query, execute_update
from core.logger import get_logger

logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def get_applied_versions() -> set[int]:
    try:
        rows = execute_query("SELECT version FROM schema_version")
        return {r["version"] for r in rows}
    except Exception:
        return set()


def run_migrations():
    if not MIGRATIONS_DIR.exists():
        logger.info("No migrations directory found, skipping")
        return

    applied = get_applied_versions()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    pending = []
    for f in migration_files:
        version = int(f.stem.split("_")[0])
        if version not in applied:
            pending.append((version, f))

    if not pending:
        logger.info("All migrations up to date")
        return

    for version, path in pending:
        sql = path.read_text(encoding="utf-8")
        name = path.stem
        logger.info(f"Running migration {version}: {name}")
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                execute_update(statement)
        execute_update(
            "INSERT INTO schema_version (version, name) VALUES (:v, :n)",
            {"v": version, "n": name},
        )
        logger.info(f"Migration {version} applied successfully")

    logger.info(f"Migrations complete: {len(pending)} applied")
