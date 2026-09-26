"""
Migration 001: Seed Initial Multi-Tenant Organizations and Role Accounts
Populates `tenants` and `users` collections in MongoDB.
No hardcoded demo accounts remain in production route handlers.
"""
from datetime import datetime
from src.database.security import hash_password

INITIAL_TENANTS = [
    {
        "tenant_id": "platform_global",
        "company_name": "Dectus HQ",
        "company_slug": "sonicsentinel-hq",
        "industry": "AI Acoustic SaaS Platform",
        "plan_tier": "enterprise_custom",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-SUPER-ADMIN-001",
        "contact_email": "admin@dectus.ai",
        "sensors_count": 48,
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-INDUS-CORP",
        "company_name": "Indus Heavy Industries",
        "company_slug": "indus-heavy",
        "industry": "Manufacturing & Industrial Plant",
        "plan_tier": "creator",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-COMP-ADMIN-001",
        "contact_email": "company@indus.com",
        "sensors_count": 18,
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-METRO-TRANSIT",
        "company_name": "Metro Transit Authority",
        "company_slug": "metro-transit",
        "industry": "Metro Transit & Public Infrastructure",
        "plan_tier": "pro",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-SEC-OP-001",
        "contact_email": "security@metro.gov",
        "sensors_count": 24,
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "b2c_residents",
        "company_name": "Dectus Personal Workspace",
        "company_slug": "sonic-personal",
        "industry": "Residential & Personal Safety",
        "plan_tier": "creator",
        "billing_cycle": "monthly",
        "subscription_status": "active",
        "admin_user_id": "USR-RESIDENT-001",
        "contact_email": "resident@city.org",
        "sensors_count": 4,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
]

INITIAL_USERS = [
    {
        "user_id": "USR-SUPER-ADMIN-001",
        "username": "admin",
        "email": "admin@dectus.ai",
        "raw_password": "admin123",
        "full_name": "Dr. Arsalan (Super Admin)",
        "role": "super_admin",
        "tenant_id": "platform_global",
        "tenant_name": "Dectus HQ",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-COMP-ADMIN-001",
        "username": "company_indus",
        "email": "company@indus.com",
        "raw_password": "company123",
        "full_name": "Tariq Malik (Company Admin)",
        "role": "company_admin",
        "tenant_id": "TENANT-INDUS-CORP",
        "tenant_name": "Indus Heavy Industries",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-SEC-OP-001",
        "username": "security_metro",
        "email": "security@metro.gov",
        "raw_password": "guard123",
        "full_name": "Officer Alex (SOC)",
        "role": "security_operator",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "tenant_name": "Metro Transit Authority",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-MAINT-OP-001",
        "username": "maintenance_indus",
        "email": "maintenance@indus.com",
        "raw_password": "engineer123",
        "full_name": "Eng. Farhan (Plant)",
        "role": "maintenance_operator",
        "tenant_id": "TENANT-INDUS-CORP",
        "tenant_name": "Indus Heavy Industries",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-REVIEWER-001",
        "username": "reviewer_hq",
        "email": "reviewer@dectus.ai",
        "raw_password": "reviewer123",
        "full_name": "Dr. Sarah (Forensic Reviewer)",
        "role": "audio_reviewer",
        "tenant_id": "platform_global",
        "tenant_name": "Dectus HQ",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-RESIDENT-001",
        "username": "resident_city",
        "email": "resident@city.org",
        "raw_password": "user123",
        "full_name": "Zainab Khan (Resident)",
        "role": "normal_user",
        "tenant_id": "b2c_residents",
        "tenant_name": "Dectus Personal Workspace",
        "onboarding_completed": True
    }
]


async def upgrade(db):
    """Applies Migration 001: Tenants and Role Users"""
    for tenant in INITIAL_TENANTS:
        await db.tenants.update_one(
            {"tenant_id": tenant["tenant_id"]},
            {"$set": tenant},
            upsert=True
        )

    for u in INITIAL_USERS:
        doc = {
            "user_id": u["user_id"],
            "username": u["username"],
            "email": u["email"],
            "password_hash": hash_password(u["raw_password"]),
            "full_name": u["full_name"],
            "role": u["role"],
            "tenant_id": u["tenant_id"],
            "tenant_name": u["tenant_name"],
            "onboarding_completed": u["onboarding_completed"],
            "is_active": True,
            "updated_at": datetime.utcnow()
        }
        await db.users.update_one(
            {"username": u["username"]},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )
