"""
Migration 003: Seed Initial Multi-Tenant Alerts, Audio Events, and Forensic Review Queue
Ensures all role dashboards display real database records immediately after migration.
"""
from datetime import datetime, timedelta

INITIAL_ALERTS = [
    {
        "alert_id": "ALT-SOC-9001",
        "audio_id": "AUD-9001",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "sound_class": "Gunshot",
        "severity": "Critical",
        "confidence": 0.96,
        "zone": "Platform 3 North Gate",
        "status": "Open",
        "target_role": "security_operator",
        "created_at": datetime.utcnow() - timedelta(minutes=14)
    },
    {
        "alert_id": "ALT-SOC-9002",
        "audio_id": "AUD-9002",
        "tenant_id": "TENANT-INDUS-CORP",
        "sound_class": "Glass Breaking",
        "severity": "High",
        "confidence": 0.91,
        "zone": "Warehouse Bay B",
        "status": "Open",
        "target_role": "security_operator",
        "created_at": datetime.utcnow() - timedelta(minutes=32)
    },
    {
        "alert_id": "ALT-MNT-9003",
        "audio_id": "AUD-9003",
        "tenant_id": "TENANT-INDUS-CORP",
        "sound_class": "Machinery Fault",
        "severity": "High",
        "confidence": 0.93,
        "zone": "Turbine Hall Sector 2",
        "status": "Open",
        "target_role": "maintenance_operator",
        "created_at": datetime.utcnow() - timedelta(minutes=45)
    },
    {
        "alert_id": "ALT-RES-9004",
        "audio_id": "AUD-9004",
        "tenant_id": "b2c_residents",
        "sound_class": "Person Asking for Help",
        "severity": "Critical",
        "confidence": 0.94,
        "zone": "Home Perimeter Sensor",
        "status": "Open",
        "target_role": "normal_user",
        "created_at": datetime.utcnow() - timedelta(minutes=8)
    }
]

INITIAL_REVIEWS = [
    {
        "review_id": "REV-8001",
        "audio_id": "AUD-8001",
        "tenant_id": "TENANT-INDUS-CORP",
        "python_prediction": "Machinery Fault",
        "python_confidence": 0.78,
        "gtm_prediction": "Vehicle Horn",
        "gtm_confidence": 0.64,
        "consistency_status": "Model Disagreement",
        "status": "Pending Review",
        "zone": "Compressor Line 4",
        "created_at": datetime.utcnow() - timedelta(minutes=22)
    },
    {
        "review_id": "REV-8002",
        "audio_id": "AUD-8002",
        "tenant_id": "platform_global",
        "python_prediction": "Panic Scream",
        "python_confidence": 0.74,
        "gtm_prediction": "Panic Scream",
        "gtm_confidence": 0.71,
        "consistency_status": "Low Confidence (<80%)",
        "status": "Pending Review",
        "zone": "Metro Concourse East",
        "created_at": datetime.utcnow() - timedelta(minutes=50)
    }
]


async def upgrade(db):
    """Applies Migration 003: Alerts and Manual Reviews"""
    for alert in INITIAL_ALERTS:
        await db.alerts.update_one(
            {"alert_id": alert["alert_id"]},
            {"$set": alert},
            upsert=True
        )

    for rev in INITIAL_REVIEWS:
        await db.manual_reviews.update_one(
            {"review_id": rev["review_id"]},
            {"$set": rev},
            upsert=True
        )
