from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class UserSchema(BaseModel):
    user_id: str
    tenant_id: str = Field("default_org", description="Organization / Tenant identifier")
    username: str
    email: str
    password_hash: str
    full_name: str
    role: str = Field(..., description="normal_user | audio_reviewer | security_operator | maintenance_operator | administrator")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

class AudioEventSchema(BaseModel):
    audio_id: str
    tenant_id: str = Field("default_org", description="Organization / Tenant identifier")
    filename: str
    file_path: Optional[str] = None
    input_source: str = Field(..., description="'upload' or 'microphone'")
    duration_seconds: float
    sample_rate: int = 16000
    channels: int = 1
    file_size_bytes: int
    quality: str = Field("Good", description="Good | Acceptable | Poor | Unusable")
    snr_db: Optional[float] = None
    is_silent: bool = False
    is_clipped: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PredictionSchema(BaseModel):
    event_id: str
    audio_id: str
    tenant_id: str = Field("default_org", description="Organization / Tenant identifier")
    python_predicted_class: str
    python_confidence: float
    python_all_confidences: Dict[str, float]
    python_model_version: str = "v1.0"
    
    gtm_predicted_class: str
    gtm_confidence: float
    gtm_all_confidences: Dict[str, float]
    gtm_model_version: str = "v1.0"
    
    model_agreement: bool
    consistency_status: str = Field(..., description="Acceptable Match | Weak Match | Model Disagreement | Uncertain Result")
    confidence_difference: float
    top_two_margin: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AlertSchema(BaseModel):
    alert_id: str
    audio_id: str
    tenant_id: str = Field("default_org", description="Organization / Tenant identifier")
    sound_category: str
    severity: str = Field(..., description="Critical | High | Medium | Low | Informational")
    recommended_action: str
    status: str = Field("New", description="New | Acknowledged | Escalated | Dismissed")
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ManualReviewSchema(BaseModel):
    review_id: str
    audio_id: str
    tenant_id: str = Field("default_org", description="Organization / Tenant identifier")
    ai_predicted_category: str
    ai_confidence: float
    ai_consistency_status: str
    review_status: str = Field("Pending", description="Pending | Confirmed | Overridden")
    final_category: Optional[str] = None
    reviewer_username: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuditLogSchema(BaseModel):
    log_id: str
    tenant_id: str = Field("default_org", description="Organization / Tenant identifier")
    action: str
    user_id: Optional[str] = "system"
    username: Optional[str] = "system"
    details: Dict[str, Any] = {}
    ip_address: Optional[str] = "127.0.0.1"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
