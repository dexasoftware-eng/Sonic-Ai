import logging
from typing import Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import settings

logger = logging.getLogger("SonicSentinel.Database")

class MongoDBManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB Atlas Cloud with graceful local fallback"""
        try:
            kwargs = {"serverSelectionTimeoutMS": 5000}
            try:
                import certifi
                kwargs["tlsCAFile"] = certifi.where()
            except ImportError:
                pass

            masked_uri = settings.MONGODB_URI.split('@')[-1] if '@' in settings.MONGODB_URI else settings.MONGODB_URI
            logger.info(f"Attempting MongoDB connection: {masked_uri}")

            self.client = AsyncIOMotorClient(settings.MONGODB_URI, **kwargs)
            self.db = self.client[settings.DATABASE_NAME]
            
            # Ping check
            await self.client.admin.command('ping')
            logger.info("Successfully connected to primary MongoDB!")

            # Create Indexes
            await self._create_indexes()

        except Exception as e:
            logger.warning(f"Primary MongoDB connection notice: {e}")
            # Graceful fallback to local MongoDB to ensure demo never fails
            if "localhost" not in settings.MONGODB_URI and "127.0.0.1" not in settings.MONGODB_URI:
                try:
                    logger.info("Attempting local MongoDB service fallback on localhost:27017...")
                    self.client = AsyncIOMotorClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
                    self.db = self.client[settings.DATABASE_NAME]
                    await self.client.admin.command('ping')
                    logger.info("Successfully connected to local fallback MongoDB!")
                    await self._create_indexes()
                except Exception as local_err:
                    logger.error(f"Both Atlas and local fallback unavailable: {local_err}")
                    self.client = None
                    self.db = None

    async def close(self):
        """Close connection on shutdown"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

    async def _create_indexes(self):
        """Create multi-tenant indexes for high performance querying on 20,000+ sound events"""
        if self.db is None:
            return
        try:
            # Users Index
            await self.db.users.create_index("username", unique=True)
            await self.db.users.create_index("email", unique=True)
            await self.db.users.create_index("tenant_id")

            # Audio Events Index (Tenant compound index)
            await self.db.audio_events.create_index("audio_id", unique=True)
            await self.db.audio_events.create_index([("tenant_id", 1), ("created_at", -1)])
            await self.db.audio_events.create_index("quality")

            # Predictions Index
            await self.db.predictions.create_index("audio_id")
            await self.db.predictions.create_index([("tenant_id", 1), ("consistency_status", 1)])

            # Alerts Index
            await self.db.alerts.create_index("alert_id", unique=True)
            await self.db.alerts.create_index([("tenant_id", 1), ("severity", 1), ("status", 1)])
            await self.db.alerts.create_index("created_at")

            # Manual Reviews Index
            await self.db.manual_reviews.create_index([("tenant_id", 1), ("status", 1)])

            # Audit Logs Index
            await self.db.audit_logs.create_index([("tenant_id", 1), ("timestamp", -1)])

            logger.info("MongoDB multi-tenant database indexes ensured.")
        except Exception as e:
            logger.warning(f"Index creation notice: {e}")

db_manager = MongoDBManager()

def get_database() -> Optional[AsyncIOMotorDatabase]:
    """Dependency for route handlers"""
    return db_manager.db
