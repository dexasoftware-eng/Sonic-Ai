import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import settings

logger = logging.getLogger("SonicSentinel.Database")


class MongoDBManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    _initialized: bool = False

    async def connect(self):
        """Connect directly to MongoDB Atlas Cloud with enterprise connection pooling and retry resilience."""
        if self.db is not None and self._initialized:
            try:
                loop = getattr(self.client, "io_loop", None)
                if loop is not None and loop.is_closed():
                    self.client = None
                    self.db = None
                    self._initialized = False
                else:
                    return
            except Exception:
                pass

        # Prepare enterprise Atlas Cloud connection options
        kwargs = {
            "serverSelectionTimeoutMS": 8000,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 30000,
            "maxPoolSize": 50,
            "minPoolSize": 5,
            "retryWrites": True,
            "retryReads": True,
        }

        try:
            import certifi
            kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass

        masked_uri = settings.MONGODB_URI.split('@')[-1] if '@' in settings.MONGODB_URI else settings.MONGODB_URI
        logger.info(f"Connecting to MongoDB Atlas Cloud: {masked_uri}")

        last_err = None
        for attempt in range(1, 4):
            try:
                self.client = AsyncIOMotorClient(settings.MONGODB_URI, **kwargs)
                self.db = self.client[settings.DATABASE_NAME]

                # Verify connection with ping
                await self.client.admin.command('ping')
                logger.info(f"Successfully connected to MongoDB Atlas Cloud ({settings.DATABASE_NAME}) on attempt {attempt}!")
                await self._create_indexes()
                self._initialized = True
                return
            except Exception as e:
                last_err = e
                logger.warning(f"Atlas connection attempt {attempt} notice: {e}")
                if attempt < 3:
                    await asyncio.sleep(1.0)

        logger.error(f"MongoDB Atlas Cloud connection failed after 3 attempts: {last_err}")
        self.client = None
        self.db = None
        self._initialized = False

    async def close(self):
        """Close connection on shutdown"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self._initialized = False
            logger.info("MongoDB Atlas Cloud connection closed.")

    async def _create_indexes(self):
        """Create multi-tenant indexes for high performance querying"""
        if self.db is None:
            return
        try:
            await self.db.users.create_index("username", unique=True, sparse=True)
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

            # Security Operations indexes
            await self.db.sensors.create_index("sensor_id", unique=True)
            await self.db.sensors.create_index([("tenant_id", 1), ("status", 1)])
            await self.db.zones.create_index("zone_id", unique=True)
            await self.db.zones.create_index([("tenant_id", 1), ("status", 1)])
            await self.db.incidents.create_index("incident_id", unique=True)
            await self.db.incidents.create_index([("tenant_id", 1), ("status", 1), ("created_at", -1)])
            await self.db.notifications.create_index([("target_tenant_id", 1), ("created_at", -1)])
            await self.db.audio_events.create_index([("tenant_id", 1), ("severity", 1)])
            await self.db.audio_events.create_index([("tenant_id", 1), ("zone_name", 1)])

            logger.info("MongoDB multi-tenant database indexes ensured.")
        except Exception as e:
            logger.warning(f"Index creation notice: {e}")


db_manager = MongoDBManager()


def get_database() -> Optional[AsyncIOMotorDatabase]:
    """O(1) non-blocking accessor for route handlers."""
    return db_manager.db


async def ensure_database() -> Optional[AsyncIOMotorDatabase]:
    """
    Fast async database accessor.
    Returns existing connected database handle immediately in O(1) once initialized.
    """
    if db_manager.db is not None and db_manager._initialized:
        try:
            loop = getattr(db_manager.client, "io_loop", None)
            if loop is not None and loop.is_closed():
                db_manager.client = None
                db_manager.db = None
                db_manager._initialized = False
            else:
                return db_manager.db
        except Exception:
            pass

    await db_manager.connect()
    return db_manager.db
