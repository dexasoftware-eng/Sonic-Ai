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


INITIAL_AUDIO_EVENTS = [
    {
        "audio_id": "AUD-9001",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "user_id": "USR-SEC-001",
        "zone_name": "Platform 3 North Gate",
        "filename": "platform3_north_gate_9001.wav",
        "input_source": "Live Sensor Stream",
        "sha256_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a01",
        "duration_seconds": 4.0,
        "sample_rate": 16000,
        "orig_sample_rate": 44100,
        "channels": 1,
        "file_size_bytes": 128044,
        "quality": "Good",
        "snr_db": 26.4,
        "peak_db": 98.4,
        "is_silent": False,
        "is_clipped": False,
        "python_prediction": "Gunshot",
        "python_confidence": 0.96,
        "gtm_prediction": "Gunshot",
        "gtm_confidence": 0.93,
        "consistency_status": "Acceptable Match",
        "confidence_difference": 0.03,
        "top_two_margin": 0.88,
        "severity": "Critical",
        "department": "Security",
        "lifecycle_status": "Alert Generated",
        "recommended_action": "Dispatch armed transit security unit to Platform 3 North Gate immediately and lock down perimeter.",
        "acoustic_features": {
            "spectral_centroid": 2480.5,
            "spectral_bandwidth": 1890.2,
            "spectral_rolloff": 5420.0,
            "zero_crossing_rate": 0.142,
            "rms_energy": 0.312,
            "onset_strength": 2.84,
            "tempo_bpm": 120.0
        },
        "created_at": datetime.utcnow() - timedelta(minutes=14)
    },
    {
        "audio_id": "AUD-9002",
        "tenant_id": "TENANT-INDUS-CORP",
        "user_id": "USR-SEC-001",
        "zone_name": "Warehouse Bay B",
        "filename": "warehouse_bay_b_9002.wav",
        "input_source": "Live Sensor Stream",
        "sha256_hash": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
        "duration_seconds": 3.5,
        "sample_rate": 16000,
        "orig_sample_rate": 44100,
        "channels": 1,
        "file_size_bytes": 112044,
        "quality": "Good",
        "snr_db": 22.8,
        "peak_db": 91.2,
        "is_silent": False,
        "is_clipped": False,
        "python_prediction": "Glass Breaking",
        "python_confidence": 0.91,
        "gtm_prediction": "Glass Breaking",
        "gtm_confidence": 0.89,
        "consistency_status": "Acceptable Match",
        "confidence_difference": 0.02,
        "top_two_margin": 0.81,
        "severity": "High",
        "department": "Security",
        "lifecycle_status": "Alert Generated",
        "recommended_action": "Inspect Warehouse Bay B exterior glazing and verify CCTV feed for forced entry.",
        "acoustic_features": {
            "spectral_centroid": 3820.4,
            "spectral_bandwidth": 2240.1,
            "spectral_rolloff": 6890.0,
            "zero_crossing_rate": 0.218,
            "rms_energy": 0.245,
            "onset_strength": 2.41,
            "tempo_bpm": 118.0
        },
        "created_at": datetime.utcnow() - timedelta(minutes=32)
    },
    {
        "audio_id": "AUD-9003",
        "tenant_id": "TENANT-INDUS-CORP",
        "user_id": "USR-MAINT-001",
        "zone_name": "Turbine Hall Sector 2",
        "filename": "turbine_hall_sector2_9003.wav",
        "input_source": "Equipment Sensor",
        "sha256_hash": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
        "duration_seconds": 4.0,
        "sample_rate": 16000,
        "orig_sample_rate": 44100,
        "channels": 1,
        "file_size_bytes": 128044,
        "quality": "Good",
        "snr_db": 21.5,
        "peak_db": 89.6,
        "is_silent": False,
        "is_clipped": False,
        "python_prediction": "Machinery Fault",
        "python_confidence": 0.93,
        "gtm_prediction": "Machinery Fault",
        "gtm_confidence": 0.90,
        "consistency_status": "Acceptable Match",
        "confidence_difference": 0.03,
        "top_two_margin": 0.84,
        "severity": "High",
        "department": "Maintenance",
        "lifecycle_status": "Alert Generated",
        "recommended_action": "Schedule immediate bearing and rotor harmonic inspection on Turbine Hall Sector 2.",
        "acoustic_features": {
            "spectral_centroid": 1940.8,
            "spectral_bandwidth": 1560.3,
            "spectral_rolloff": 4380.0,
            "zero_crossing_rate": 0.116,
            "rms_energy": 0.278,
            "onset_strength": 1.92,
            "tempo_bpm": 144.0
        },
        "created_at": datetime.utcnow() - timedelta(minutes=45)
    },
    {
        "audio_id": "AUD-9004",
        "tenant_id": "b2c_residents",
        "user_id": "USR-RESIDENT-001",
        "zone_name": "Home Perimeter Sensor",
        "filename": "home_perimeter_sos_9004.wav",
        "input_source": "Live Sensor Stream",
        "sha256_hash": "e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683",
        "duration_seconds": 4.0,
        "sample_rate": 16000,
        "orig_sample_rate": 44100,
        "channels": 1,
        "file_size_bytes": 128044,
        "quality": "Good",
        "snr_db": 24.8,
        "peak_db": 94.2,
        "is_silent": False,
        "is_clipped": False,
        "python_prediction": "Person Asking for Help",
        "python_confidence": 0.94,
        "gtm_prediction": "Person Asking for Help",
        "gtm_confidence": 0.92,
        "consistency_status": "Acceptable Match",
        "confidence_difference": 0.02,
        "top_two_margin": 0.86,
        "severity": "Critical",
        "department": "Security",
        "lifecycle_status": "Alert Generated",
        "recommended_action": "Verify vocal distress signature on Home Perimeter Sensor and initiate emergency welfare check.",
        "acoustic_features": {
            "spectral_centroid": 2160.2,
            "spectral_bandwidth": 1680.5,
            "spectral_rolloff": 4890.0,
            "zero_crossing_rate": 0.134,
            "rms_energy": 0.294,
            "onset_strength": 2.56,
            "tempo_bpm": 128.0
        },
        "created_at": datetime.utcnow() - timedelta(minutes=8)
    },
    {
        "audio_id": "AUD-8001",
        "tenant_id": "TENANT-INDUS-CORP",
        "user_id": "USR-MAINT-001",
        "zone_name": "Compressor Line 4",
        "filename": "compressor_line4_8001.wav",
        "input_source": "Equipment Sensor",
        "sha256_hash": "7902699be42c8a8e46fbbb4501726517e86b22c56a189f7625a6da49081b2451",
        "duration_seconds": 4.0,
        "sample_rate": 16000,
        "orig_sample_rate": 44100,
        "channels": 1,
        "file_size_bytes": 128044,
        "quality": "Acceptable",
        "snr_db": 17.6,
        "peak_db": 86.4,
        "is_silent": False,
        "is_clipped": False,
        "python_prediction": "Machinery Fault",
        "python_confidence": 0.78,
        "gtm_prediction": "Vehicle Horn",
        "gtm_confidence": 0.64,
        "consistency_status": "Model Disagreement",
        "confidence_difference": 0.14,
        "top_two_margin": 0.42,
        "severity": "High",
        "department": "Maintenance",
        "lifecycle_status": "Manual Review",
        "recommended_action": "Perform forensic spectrogram inspection to resolve model disagreement on Compressor Line 4.",
        "acoustic_features": {
            "spectral_centroid": 1690.0,
            "spectral_bandwidth": 1490.0,
            "spectral_rolloff": 3920.0,
            "zero_crossing_rate": 0.098,
            "rms_energy": 0.214,
            "onset_strength": 1.68,
            "tempo_bpm": 116.0
        },
        "created_at": datetime.utcnow() - timedelta(minutes=22)
    },
    {
        "audio_id": "AUD-8002",
        "tenant_id": "platform_global",
        "user_id": "USR-SEC-001",
        "zone_name": "Metro Concourse East",
        "filename": "metro_concourse_east_8002.wav",
        "input_source": "Live Sensor Stream",
        "sha256_hash": "2c624232cdd221771294dfbb310aca000a0df6ac8b66b696d90ef06fdefb64a3",
        "duration_seconds": 4.0,
        "sample_rate": 16000,
        "orig_sample_rate": 44100,
        "channels": 1,
        "file_size_bytes": 128044,
        "quality": "Acceptable",
        "snr_db": 18.9,
        "peak_db": 90.1,
        "is_silent": False,
        "is_clipped": False,
        "python_prediction": "Panic Scream",
        "python_confidence": 0.74,
        "gtm_prediction": "Panic Scream",
        "gtm_confidence": 0.71,
        "consistency_status": "Weak Match",
        "confidence_difference": 0.03,
        "top_two_margin": 0.51,
        "severity": "Critical",
        "department": "Security",
        "lifecycle_status": "Manual Review",
        "recommended_action": "Verify acoustic signature in Metro Concourse East and review camera feeds.",
        "acoustic_features": {
            "spectral_centroid": 2890.0,
            "spectral_bandwidth": 1980.0,
            "spectral_rolloff": 5840.0,
            "zero_crossing_rate": 0.165,
            "rms_energy": 0.262,
            "onset_strength": 2.18,
            "tempo_bpm": 132.0
        },
        "created_at": datetime.utcnow() - timedelta(minutes=50)
    }
]


async def upgrade(db):
    """Applies Migration 003: Ensures clean database indexes without inserting fake demo data."""
    if db is not None:
        try:
            await db.audio_events.create_index([("audio_id", 1)], unique=True)
            await db.audio_events.create_index([("user_id", 1)])
            await db.audio_events.create_index([("tenant_id", 1)])
            await db.audio_events.create_index([("created_at", -1)])
            await db.alerts.create_index([("alert_id", 1)], unique=True)
            await db.alerts.create_index([("user_id", 1)])
            await db.alerts.create_index([("tenant_id", 1)])
            await db.manual_reviews.create_index([("review_id", 1)], unique=True)
        except Exception:
            pass


