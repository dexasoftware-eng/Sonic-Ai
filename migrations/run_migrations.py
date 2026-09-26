"""
Database Migration Runner for SonicSentinel AI
Executes all numbered migrations in `migrations/` against the active MongoDB database.
"""
import asyncio
import importlib.util
import logging
from pathlib import Path
from datetime import datetime

from src.database.mongodb import db_manager, get_database

logger = logging.getLogger("SonicSentinel.Migrations")


async def run_all_migrations(db=None) -> dict:
    """Runs all migration scripts in alphabetical order and records state in `db.schema_migrations`."""
    own_connection = False
    if db is None:
        await db_manager.connect()
        db = get_database()
        own_connection = True

    if db is None:
        raise RuntimeError("Database connection unavailable — cannot run migrations.")

    migrations_dir = Path(__file__).resolve().parent
    migration_files = sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.py"))
    applied = []

    for mig_file in migration_files:
        spec = importlib.util.spec_from_file_location(mig_file.stem, str(mig_file))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "upgrade"):
            logger.info(f"Applying migration: {mig_file.name}")
            await module.upgrade(db)
            await db.schema_migrations.update_one(
                {"migration": mig_file.name},
                {"$set": {"migration": mig_file.name, "applied_at": datetime.utcnow()}},
                upsert=True
            )
            applied.append(mig_file.name)

    if own_connection:
        await db_manager.close()

    return {"status": "success", "applied_migrations": applied}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_all_migrations())
    print("Migrations Complete:", result)
