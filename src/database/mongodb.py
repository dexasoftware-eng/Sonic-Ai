import os
import time
import socket
import logging
import subprocess
from pathlib import Path
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import settings

logger = logging.getLogger("SonicSentinel.Database")


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _ensure_local_mongod_running() -> bool:
    """Starts local MongoDB 8.x server in user-space if port 27017 is not open."""
    if _is_port_open("127.0.0.1", 27017):
        return True

    mongod_candidates = [
        Path(r"C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe"),
        Path(r"C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe"),
        Path(r"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe"),
    ]
    mongod_exe = next((p for p in mongod_candidates if p.exists()), None)
    if not mongod_exe:
        return False

    db_path = settings.BASE_DIR / "data" / "mongodb"
    log_path = db_path / "mongod.log"
    db_path.mkdir(parents=True, exist_ok=True)

    # Clean up any stale FTDC interim files if present
    ftdc_dir = db_path / "diagnostic.data"
    if ftdc_dir.exists():
        for f in ftdc_dir.glob("metrics.interim*"):
            try:
                f.unlink()
            except Exception:
                pass

    try:
        logger.info(f"Starting local MongoDB engine ({mongod_exe.name}) on port 27017...")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        subprocess.Popen(
            [
                str(mongod_exe),
                "--dbpath", str(db_path),
                "--port", "27017",
                "--bind_ip", "127.0.0.1",
                "--logpath", str(log_path),
                "--logappend"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        for _ in range(35):
            if _is_port_open("127.0.0.1", 27017):
                return True
            time.sleep(0.3)
    except Exception as e:
        logger.error(f"Failed to start local mongod process: {e}")

    return _is_port_open("127.0.0.1", 27017)


class MongoDBManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB (auto-starts local MongoDB 8.3 engine if needed)"""
        try:
            if "127.0.0.1" in settings.MONGODB_URI or "localhost" in settings.MONGODB_URI:
                _ensure_local_mongod_running()

            kwargs = {"serverSelectionTimeoutMS": 4000}
            if "mongodb+srv" in settings.MONGODB_URI or "tls=true" in settings.MONGODB_URI:
                try:
                    import certifi
                    kwargs["tlsCAFile"] = certifi.where()
                except ImportError:
                    pass

            masked_uri = settings.MONGODB_URI.split('@')[-1] if '@' in settings.MONGODB_URI else settings.MONGODB_URI
            logger.info(f"Attempting MongoDB connection: {masked_uri}")

            self.client = AsyncIOMotorClient(settings.MONGODB_URI, **kwargs)
            self.db = self.client[settings.DATABASE_NAME]

            await self.client.admin.command('ping')
            logger.info("Successfully connected to primary MongoDB!")
            await self._create_indexes()

        except Exception as e:
            logger.warning(f"Primary MongoDB connection notice: {e}")
            try:
                _ensure_local_mongod_running()
                logger.info("Connecting to local MongoDB service on 127.0.0.1:27017...")
                self.client = AsyncIOMotorClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=4000)
                self.db = self.client[settings.DATABASE_NAME]
                await self.client.admin.command('ping')
                logger.info("Successfully connected to local MongoDB (127.0.0.1:27017)!")
                await self._create_indexes()
            except Exception as local_err:
                logger.error(f"MongoDB connection unavailable: {local_err}")
                self.client = None
                self.db = None

    async def close(self):
        """Close connection on shutdown"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

    async def _create_indexes(self):
        """Create multi-tenant indexes for high performance querying"""
        if self.db is None:
            return
        try:
            await self.db.users.create_index("username", unique=True)
            await self.db.users.create_index("email", unique=True)
            await self.db.users.create_index("tenant_id")

            await self.db.tenants.create_index("tenant_id", unique=True)
            await self.db.tenants.create_index("company_slug")

            await self.db.subscription_plans.create_index("plan_id", unique=True)

            await self.db.audio_events.create_index("audio_id", unique=True)
            await self.db.audio_events.create_index([("tenant_id", 1), ("created_at", -1)])
            await self.db.audio_events.create_index("quality")

            await self.db.predictions.create_index("audio_id")
            await self.db.predictions.create_index([("tenant_id", 1), ("consistency_status", 1)])

            await self.db.alerts.create_index("alert_id", unique=True)
            await self.db.alerts.create_index([("tenant_id", 1), ("severity", 1), ("status", 1)])
            await self.db.alerts.create_index("created_at")

            await self.db.manual_reviews.create_index([("tenant_id", 1), ("status", 1)])
            await self.db.audit_logs.create_index([("tenant_id", 1), ("timestamp", -1)])

            logger.info("MongoDB multi-tenant database indexes ensured.")
        except Exception as e:
            logger.warning(f"Index creation notice: {e}")


db_manager = MongoDBManager()


def get_database() -> Optional[AsyncIOMotorDatabase]:
    """Synchronous accessor for route handlers"""
    if not _is_port_open("127.0.0.1", 27017):
        _ensure_local_mongod_running()
    return db_manager.db


async def ensure_database() -> Optional[AsyncIOMotorDatabase]:
    """
    Async self-healing database accessor.
    Ensures local mongod is running, reconnects Motor client if needed,
    and seeds migrations if the users collection is empty.
    """
    if not _is_port_open("127.0.0.1", 27017) or db_manager.db is None:
        _ensure_local_mongod_running()
        await db_manager.connect()

    if db_manager.db is not None:
        try:
            await db_manager.client.admin.command("ping")
            user_count = await db_manager.db.users.count_documents({}, limit=1)
            if user_count == 0:
                from migrations.runner import run_all_migrations
                await run_all_migrations(db_manager.db)
        except Exception:
            _ensure_local_mongod_running()
            await db_manager.connect()

    return db_manager.db
