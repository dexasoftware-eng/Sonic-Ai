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
        "company_slug": "dectus-hq",
        "industry": "Enterprise Acoustic Security Platform",
        "plan_id": "comp_pro",
        "plan_tier": "enterprise_custom",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-SUPER-ADMIN-001",
        "admin_name": "Dr. Arsalan",
        "contact_email": "admin@sonicsentinel.ai",
        "sensors_count": 48,
        "credits_used": 1420800,
        "stripe_customer_id": "cus_HqMaster001",
        "stripe_subscription_id": "sub_1P9kHqMaster01",
        "payment_method": "Corporate Treasury Wire",
        "renewal_date": "Jan 01, 2027",
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-INDUS-CORP",
        "company_name": "Indus Heavy Industries",
        "company_slug": "indus-heavy",
        "industry": "Manufacturing & Industrial Plant",
        "plan_id": "comp_creator",
        "plan_tier": "creator",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-COMP-ADMIN-001",
        "admin_name": "Tariq Malik",
        "contact_email": "company@indus.com",
        "sensors_count": 18,
        "credits_used": 642500,
        "stripe_customer_id": "cus_Qx92Indus88",
        "stripe_subscription_id": "sub_1P9kL2Indus88",
        "payment_method": "Visa •••• 4242",
        "renewal_date": "Nov 15, 2026",
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-METRO-TRANSIT",
        "company_name": "Metro Transit Authority",
        "company_slug": "metro-transit",
        "industry": "Metro Transit & Public Infrastructure",
        "plan_id": "comp_pro",
        "plan_tier": "pro",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-SEC-OP-001",
        "admin_name": "Marcus Vance",
        "contact_email": "security@metro.gov",
        "sensors_count": 64,
        "credits_used": 2840900,
        "stripe_customer_id": "cus_Metro94Tr02",
        "stripe_subscription_id": "sub_1P8mR4Metro02",
        "payment_method": "ACH Corporate Wire •••• 9012",
        "renewal_date": "Dec 01, 2026",
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-APEX-LOGISTICS",
        "company_name": "Apex Global Logistics",
        "company_slug": "apex-logistics",
        "industry": "Supply Chain & Port Warehousing",
        "plan_id": "comp_creator",
        "plan_tier": "creator",
        "billing_cycle": "monthly",
        "subscription_status": "active",
        "admin_user_id": "USR-COMP-ADMIN-002",
        "admin_name": "Elena Vance",
        "contact_email": "elena.vance@apexlogistics.com",
        "sensors_count": 14,
        "credits_used": 495200,
        "stripe_customer_id": "cus_Apex77Log03",
        "stripe_subscription_id": "sub_1P9pApex77Log",
        "payment_method": "Mastercard •••• 8819",
        "renewal_date": "Oct 28, 2026",
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-VANGUARD-ENERGY",
        "company_name": "Vanguard Energy Grid",
        "company_slug": "vanguard-energy",
        "industry": "Power Substation & Utility Infrastructure",
        "plan_id": "comp_pro",
        "plan_tier": "pro",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "admin_user_id": "USR-COMP-ADMIN-003",
        "admin_name": "Robert Chen",
        "contact_email": "ops-billing@vanguardgrid.io",
        "sensors_count": 42,
        "credits_used": 1915400,
        "stripe_customer_id": "cus_Vang55Grid04",
        "stripe_subscription_id": "sub_1P7vVang55Grd",
        "payment_method": "Amex Corporate •••• 3004",
        "renewal_date": "Jan 18, 2027",
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "TENANT-PACIFIC-PORT",
        "company_name": "Pacific Port Terminal",
        "company_slug": "pacific-port",
        "industry": "Maritime Container & Perimeter Security",
        "plan_id": "comp_starter",
        "plan_tier": "starter",
        "billing_cycle": "monthly",
        "subscription_status": "active",
        "admin_user_id": "USR-COMP-ADMIN-004",
        "admin_name": "Capt. David Miller",
        "contact_email": "security@pacificport.org",
        "sensors_count": 5,
        "credits_used": 212800,
        "stripe_customer_id": "cus_PacPort19 Term",
        "stripe_subscription_id": "sub_1P9tPacPort19",
        "payment_method": "Visa •••• 6108",
        "renewal_date": "Oct 24, 2026",
        "created_at": datetime.utcnow(),
        "is_active": True
    },
    {
        "tenant_id": "b2c_residents",
        "company_name": "Dectus Personal Workspace",
        "company_slug": "dectus-personal",
        "industry": "Residential & Personal Safety",
        "plan_id": "ind_creator",
        "plan_tier": "creator",
        "billing_cycle": "monthly",
        "subscription_status": "active",
        "admin_user_id": "USR-RESIDENT-001",
        "contact_email": "resident@city.org",
        "sensors_count": 4,
        "credits_used": 78400,
        "stripe_customer_id": "cus_ResNet001",
        "stripe_subscription_id": "sub_1P9kResNet001",
        "payment_method": "Visa •••• 4242",
        "renewal_date": "Oct 28, 2026",
        "created_at": datetime.utcnow(),
        "is_active": True
    }
]

INITIAL_USERS = [
    {
        "user_id": "USR-SUPER-ADMIN-001",
        "username": "admin",
        "email": "admin@sonicsentinel.ai",
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
        "user_id": "USR-COMP-ADMIN-002",
        "username": "company_apex",
        "email": "elena.vance@apexlogistics.com",
        "raw_password": "company123",
        "full_name": "Elena Vance (Company Admin)",
        "role": "company_admin",
        "tenant_id": "TENANT-APEX-LOGISTICS",
        "tenant_name": "Apex Global Logistics",
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
        "email": "reviewer@sonicsentinel.ai",
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
        "full_name": "Zainab Khan",
        "role": "normal_user",
        "tenant_id": "b2c_residents",
        "tenant_name": "Individual Subscriber",
        "plan_id": "ind_creator",
        "plan_tier": "creator",
        "billing_cycle": "monthly",
        "subscription_status": "active",
        "credits_used": 84600,
        "stripe_customer_id": "cus_Res901Zk",
        "stripe_subscription_id": "sub_1P9uZk901",
        "payment_method": "Visa •••• 4242",
        "renewal_date": "Oct 28, 2026",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-RESIDENT-002",
        "username": "david_thorne",
        "email": "d.thorne@metrohome.io",
        "raw_password": "user123",
        "full_name": "David Thorne",
        "role": "normal_user",
        "tenant_id": "b2c_residents",
        "tenant_name": "Individual Subscriber",
        "plan_id": "ind_pro",
        "plan_tier": "pro",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "credits_used": 412800,
        "stripe_customer_id": "cus_Res902Dt",
        "stripe_subscription_id": "sub_1P9uDt902",
        "payment_method": "Mastercard •••• 5521",
        "renewal_date": "Dec 14, 2026",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-RESIDENT-003",
        "username": "hannah_abbott",
        "email": "hannah.abbott@oakridge.org",
        "raw_password": "user123",
        "full_name": "Hannah Abbott",
        "role": "normal_user",
        "tenant_id": "b2c_residents",
        "tenant_name": "Individual Subscriber",
        "plan_id": "ind_starter",
        "plan_tier": "starter",
        "billing_cycle": "monthly",
        "subscription_status": "active",
        "credits_used": 19450,
        "stripe_customer_id": "cus_Res903Ha",
        "stripe_subscription_id": "sub_1P9uHa903",
        "payment_method": "Apple Pay •••• 1094",
        "renewal_date": "Oct 21, 2026",
        "onboarding_completed": True
    },
    {
        "user_id": "USR-RESIDENT-004",
        "username": "carlos_mendez",
        "email": "cmendez@harborview.net",
        "raw_password": "user123",
        "full_name": "Carlos Mendez",
        "role": "normal_user",
        "tenant_id": "b2c_residents",
        "tenant_name": "Individual Subscriber",
        "plan_id": "ind_creator",
        "plan_tier": "creator",
        "billing_cycle": "yearly",
        "subscription_status": "active",
        "credits_used": 96200,
        "stripe_customer_id": "cus_Res904Cm",
        "stripe_subscription_id": "sub_1P9uCm904",
        "payment_method": "Visa •••• 7731",
        "renewal_date": "Nov 09, 2026",
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
        for extra_k in ("plan_id", "plan_tier", "billing_cycle", "subscription_status", "credits_used", "stripe_customer_id", "stripe_subscription_id", "payment_method", "renewal_date"):
            if extra_k in u:
                doc[extra_k] = u[extra_k]
        await db.users.update_one(
            {"username": u["username"]},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )

