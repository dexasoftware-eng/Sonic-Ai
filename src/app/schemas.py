from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr

class CompanyTenantSchema(BaseModel):
    tenant_id: str = Field(..., description="Unique organization / tenant ID")
    company_name: str
    company_slug: str
    industry: str = Field("General Commercial", description="Manufacturing, Transit, Commercial, Campus, Healthcare")
    plan_tier: str = Field("enterprise_starter", description="enterprise_starter | enterprise_pro | enterprise_custom")
    stripe_customer_id: Optional[str] = None
    subscription_status: str = Field("active", description="active | trial | past_due | cancelled")
    admin_user_id: str
    contact_email: str
    sensors_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

class ResidentRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    username: Optional[str] = None
    residential_area: Optional[str] = "Metropolitan Area"

class CompanyRegisterRequest(BaseModel):
    company_name: str
    industry: str
    work_email: str
    admin_name: str
    password: str
    username: Optional[str] = None

class LoginRequest(BaseModel):
    username_or_email: str
    password: str
    remember_me: bool = False

class StaffInviteRequest(BaseModel):
    tenant_id: str
    full_name: str
    email: str
    role: str = Field(..., description="security_operator | maintenance_operator | audio_reviewer")

class SubscriptionPlanSchema(BaseModel):
    plan_id: str
    name: str
    type: str = Field(..., description="'individual' (B2C) or 'company' (B2B)")
    price_usd_monthly: float
    description: str
    features: List[str]
