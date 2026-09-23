import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health_endpoint():
    """Test health check route returns all 10 mandatory classes"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mandatory_classes_count"] == 10
    assert "Gunshot" in data["classes"]
    assert "Glass Breaking" in data["classes"]

def test_root_dashboard_endpoint():
    """Test web dashboard HTML page renders correctly"""
    response = client.get("/")
    assert response.status_code == 200
    assert "SonicSentinel" in response.text
    assert "waveformCanvas" in response.text

def test_audio_upload_classification():
    """Test uploading a gunshot audio sample returns valid dual-model inference"""
    sample_file = Path("sample_audio/gunshot.wav")
    assert sample_file.exists()

    with open(sample_file, "rb") as f:
        response = client.post(
            "/api/audio/upload",
            files={"file": ("gunshot.wav", f, "audio/wav")}
        )

    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert "python_model" in res
    assert "gtm_model" in res
    assert "consensus" in res
    assert res["consensus"]["severity"] in ["Critical", "High", "Medium", "Low", "Informational"]
