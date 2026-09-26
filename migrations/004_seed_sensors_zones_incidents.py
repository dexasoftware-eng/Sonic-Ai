"""
Migration 004: Seed Real Sensors, Monitored Zones, and Incidents Queue
Ensures the Security Operations Center (SOC) role has real, persistent MongoDB records
for sensors, perimeter zones, and tracked incidents with strict multi-tenant isolation.
"""
from datetime import datetime, timedelta

INITIAL_ZONES = [
    {
        "zone_id": "ZONE-METRO-01",
        "name": "Platform 3 North Gate",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "building_area": "Transit Concourse North",
        "threat_level": "critical",
        "status": "active",
        "description": "High-density passenger ingress gate with impulsive shockwave acoustic monitors.",
        "sensors_count": 4,
        "created_at": datetime.utcnow() - timedelta(days=45)
    },
    {
        "zone_id": "ZONE-METRO-02",
        "name": "East Concourse Mezzanine",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "building_area": "Ticketing & Retail Arcade",
        "threat_level": "normal",
        "status": "active",
        "description": "Public lobby area with vocal distress and ambient crowd monitoring.",
        "sensors_count": 3,
        "created_at": datetime.utcnow() - timedelta(days=45)
    },
    {
        "zone_id": "ZONE-METRO-03",
        "name": "Maintenance Yard Sector 4",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "building_area": "Rolling Stock Depot",
        "threat_level": "elevated",
        "status": "active",
        "description": "Heavy rail switching perimeter with continuous acoustic tripwires.",
        "sensors_count": 3,
        "created_at": datetime.utcnow() - timedelta(days=30)
    },
    {
        "zone_id": "ZONE-INDUS-01",
        "name": "Warehouse Bay B",
        "tenant_id": "TENANT-INDUS-CORP",
        "building_area": "Logistics & Loading Dock",
        "threat_level": "high",
        "status": "active",
        "description": "Perimeter glass-break and forced intrusion detection nodes.",
        "sensors_count": 5,
        "created_at": datetime.utcnow() - timedelta(days=60)
    },
    {
        "zone_id": "ZONE-INDUS-02",
        "name": "Turbine Hall Sector 2",
        "tenant_id": "TENANT-INDUS-CORP",
        "building_area": "Power Generation Wing",
        "threat_level": "high",
        "status": "active",
        "description": "Heavy rotating machinery acoustic anomaly and vibration telemetry.",
        "sensors_count": 6,
        "created_at": datetime.utcnow() - timedelta(days=60)
    },
    {
        "zone_id": "ZONE-GLOBAL-01",
        "name": "Perimeter Security Ring Alpha",
        "tenant_id": "platform_global",
        "building_area": "Global Command Omnibox",
        "threat_level": "elevated",
        "status": "active",
        "description": "Enterprise headquarters exterior fence line acoustic sensor ring.",
        "sensors_count": 8,
        "created_at": datetime.utcnow() - timedelta(days=90)
    }
]

INITIAL_SENSORS = [
    {
        "sensor_id": "SNS-METRO-01",
        "name": "North Gate Mic Array 01",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "zone_id": "ZONE-METRO-01",
        "zone_name": "Platform 3 North Gate",
        "status": "online",
        "audio_health": "optimal",
        "connection_health": "stable",
        "hardware_model": "SonicNode-Array-X4",
        "sample_rate": 16000,
        "ip_address": "10.20.14.101",
        "last_seen": datetime.utcnow() - timedelta(seconds=12),
        "last_detection_class": "Gunshot",
        "last_detection_time": datetime.utcnow() - timedelta(minutes=14),
        "created_at": datetime.utcnow() - timedelta(days=40)
    },
    {
        "sensor_id": "SNS-METRO-02",
        "name": "Turnstile Acoustic Pod 02",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "zone_id": "ZONE-METRO-01",
        "zone_name": "Platform 3 North Gate",
        "status": "online",
        "audio_health": "optimal",
        "connection_health": "stable",
        "hardware_model": "SonicNode-Array-X4",
        "sample_rate": 16000,
        "ip_address": "10.20.14.102",
        "last_seen": datetime.utcnow() - timedelta(seconds=28),
        "last_detection_class": "Person Asking for Help",
        "last_detection_time": datetime.utcnow() - timedelta(minutes=52),
        "created_at": datetime.utcnow() - timedelta(days=40)
    },
    {
        "sensor_id": "SNS-METRO-03",
        "name": "Platform Edge Sensor 03",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "zone_id": "ZONE-METRO-01",
        "zone_name": "Platform 3 North Gate",
        "status": "degraded",
        "audio_health": "clipped",
        "connection_health": "intermittent",
        "hardware_model": "SonicNode-Array-X4",
        "sample_rate": 16000,
        "ip_address": "10.20.14.103",
        "last_seen": datetime.utcnow() - timedelta(minutes=6),
        "last_detection_class": "Normal Ambient",
        "last_detection_time": datetime.utcnow() - timedelta(hours=3),
        "created_at": datetime.utcnow() - timedelta(days=40)
    },
    {
        "sensor_id": "SNS-METRO-04",
        "name": "Concourse Overhead Mic 04",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "zone_id": "ZONE-METRO-02",
        "zone_name": "East Concourse Mezzanine",
        "status": "online",
        "audio_health": "optimal",
        "connection_health": "stable",
        "hardware_model": "SonicNode-Mini-M2",
        "sample_rate": 16000,
        "ip_address": "10.20.14.104",
        "last_seen": datetime.utcnow() - timedelta(seconds=45),
        "last_detection_class": "Normal Crowd",
        "last_detection_time": datetime.utcnow() - timedelta(hours=1),
        "created_at": datetime.utcnow() - timedelta(days=35)
    },
    {
        "sensor_id": "SNS-METRO-05",
        "name": "Yard Tripwire Sensor 05",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "zone_id": "ZONE-METRO-03",
        "zone_name": "Maintenance Yard Sector 4",
        "status": "offline",
        "audio_health": "unreachable",
        "connection_health": "unreachable",
        "hardware_model": "SonicNode-Rugged-R1",
        "sample_rate": 16000,
        "ip_address": "10.20.14.105",
        "last_seen": datetime.utcnow() - timedelta(hours=2, minutes=15),
        "last_detection_class": "Vehicle Backfire",
        "last_detection_time": datetime.utcnow() - timedelta(hours=4),
        "created_at": datetime.utcnow() - timedelta(days=25)
    },
    {
        "sensor_id": "SNS-INDUS-01",
        "name": "Bay B Glass Acoustic Node",
        "tenant_id": "TENANT-INDUS-CORP",
        "zone_id": "ZONE-INDUS-01",
        "zone_name": "Warehouse Bay B",
        "status": "online",
        "audio_health": "optimal",
        "connection_health": "stable",
        "hardware_model": "SonicNode-Industrial-I2",
        "sample_rate": 16000,
        "ip_address": "192.168.10.12",
        "last_seen": datetime.utcnow() - timedelta(seconds=15),
        "last_detection_class": "Glass Breaking",
        "last_detection_time": datetime.utcnow() - timedelta(minutes=32),
        "created_at": datetime.utcnow() - timedelta(days=50)
    },
    {
        "sensor_id": "SNS-INDUS-02",
        "name": "Turbine Hall Mic 01",
        "tenant_id": "TENANT-INDUS-CORP",
        "zone_id": "ZONE-INDUS-02",
        "zone_name": "Turbine Hall Sector 2",
        "status": "online",
        "audio_health": "nominal",
        "connection_health": "stable",
        "hardware_model": "SonicNode-Industrial-I2",
        "sample_rate": 16000,
        "ip_address": "192.168.10.15",
        "last_seen": datetime.utcnow() - timedelta(seconds=5),
        "last_detection_class": "Machinery Fault",
        "last_detection_time": datetime.utcnow() - timedelta(minutes=45),
        "created_at": datetime.utcnow() - timedelta(days=50)
    }
]

INITIAL_INCIDENTS = [
    {
        "incident_id": "INC-SOC-001",
        "alert_id": "ALT-SOC-9001",
        "audio_id": "AUD-9001",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "title": "Perimeter Gunshot Impulse Detected",
        "severity": "Critical",
        "status": "New",
        "zone_id": "ZONE-METRO-01",
        "zone_name": "Platform 3 North Gate",
        "sensor_id": "SNS-METRO-01",
        "sound_class": "Gunshot",
        "confidence": 0.96,
        "consensus_status": "Acceptable Match",
        "assigned_operator": "Officer Alex (SOC)",
        "notes": "Shockwave transient captured on sensor SNS-METRO-01. Dual-AI model validated 96.2% confidence.",
        "timeline": [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=14)).isoformat(),
                "actor": "System Autonomous Engine",
                "action": "Incident Created",
                "note": "Triggered by Critical Alert ALT-SOC-9001"
            }
        ],
        "created_at": datetime.utcnow() - timedelta(minutes=14),
        "updated_at": datetime.utcnow() - timedelta(minutes=14)
    },
    {
        "incident_id": "INC-SOC-002",
        "alert_id": "ALT-SOC-9002",
        "audio_id": "AUD-9002",
        "tenant_id": "TENANT-INDUS-CORP",
        "title": "Warehouse Perimeter Forced Entry / Glass Break",
        "severity": "High",
        "status": "Acknowledged",
        "zone_id": "ZONE-INDUS-01",
        "zone_name": "Warehouse Bay B",
        "sensor_id": "SNS-INDUS-01",
        "sound_class": "Glass Breaking",
        "confidence": 0.91,
        "consensus_status": "Acceptable Match",
        "assigned_operator": "Tariq Malik (Company Admin)",
        "notes": "High frequency resonance indicative of tempered glass breach.",
        "timeline": [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=32)).isoformat(),
                "actor": "System Autonomous Engine",
                "action": "Incident Created",
                "note": "Triggered by High Alert ALT-SOC-9002"
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=24)).isoformat(),
                "actor": "Tariq Malik (Company Admin)",
                "action": "Acknowledged",
                "note": "Dispatching security patrol to Warehouse Bay B."
            }
        ],
        "created_at": datetime.utcnow() - timedelta(minutes=32),
        "updated_at": datetime.utcnow() - timedelta(minutes=24)
    }
]


async def upgrade(db):
    """Applies Migration 004: Sensors, Zones, and Incident Queue"""
    for z in INITIAL_ZONES:
        await db.zones.update_one(
            {"zone_id": z["zone_id"]},
            {"$set": z},
            upsert=True
        )

    for s in INITIAL_SENSORS:
        await db.sensors.update_one(
            {"sensor_id": s["sensor_id"]},
            {"$set": s},
            upsert=True
        )

    for inc in INITIAL_INCIDENTS:
        await db.incidents.update_one(
            {"incident_id": inc["incident_id"]},
            {"$set": inc},
            upsert=True
        )
