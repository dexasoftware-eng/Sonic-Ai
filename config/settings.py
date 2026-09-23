import os
import json
from pathlib import Path
from typing import Dict, Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "SonicSentinel AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "sonic-sentinel-techwiz-secret-key-2026"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MongoDB Configuration
    # Supports MongoDB Atlas (mongodb+srv://...) as well as local MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "sonic_sentinel_db"

    # Audio Pipeline Configuration
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    WINDOW_DURATION_SEC: float = 2.0
    N_MFCC: int = 40
    N_MELS: int = 128

    # Paths
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    SAMPLE_AUDIO_DIR: Path = BASE_DIR / "sample_audio"
    DATASET_DIR: Path = BASE_DIR / "data" / "audio_dataset"
    RULES_FILE: Path = BASE_DIR / "config" / "rules.json"
    SAVED_MODELS_DIR: Path = BASE_DIR / "src" / "models" / "saved_models"
    GTM_MODEL_DIR: Path = BASE_DIR / "src" / "models" / "gtm_files"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure necessary runtime directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.SAVED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
settings.GTM_MODEL_DIR.mkdir(parents=True, exist_ok=True)

MANDATORY_CLASSES: List[str] = [
    "Machinery Fault",
    "Glass Breaking",
    "Alarm or Siren",
    "Vehicle Horn",
    "Animal Sound",
    "Gunshot",
    "Panic Scream",
    "Aggression",
    "Person Asking for Help",
    "Background Noise"
]

def load_rules() -> Dict[str, Any]:
    """Loads system alert rules and categories from config/rules.json"""
    with open(settings.RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_mandatory_classes() -> List[str]:
    """Returns the 10 official competition mandatory sound categories"""
    return list(MANDATORY_CLASSES)

def get_registered_classes() -> List[str]:
    """Returns list of all registered sound categories (including dynamic/custom additions)"""
    rules = load_rules()
    return [cat["name"] for cat in rules.get("sound_categories", [])]

