"""
Migration 002: Seed Subscription Plans (Individual & Enterprise Tiers)
Populates `subscription_plans` collection in MongoDB.
"""
from datetime import datetime

SUBSCRIPTION_PLANS = [
    {
        "plan_id": "ind_starter",
        "workspace_type": "individual",
        "audience": "individual",
        "name": "Starter",
        "price_monthly_usd": 6.0,
        "price_yearly_usd": 5.0,
        "popular": False,
        "first_month_half_price": False,
        "credits_per_month": 30000,
        "max_staff_seats": 1,
        "max_zones": 1,
        "retention_days": 14,
        "sla_tier": "99.5% Standard",
        "stripe_price_id_monthly": "price_1P9kIndStarterMo",
        "stripe_price_id_yearly": "price_1P9kIndStarterYr",
        "features": [
            "30,000 monthly processing credits",
            "10 core acoustic detection categories",
            "Real-time stream & file upload ingestion",
            "14-day event log retention"
        ]
    },
    {
        "plan_id": "ind_creator",
        "workspace_type": "individual",
        "audience": "individual",
        "name": "Creator",
        "price_monthly_usd": 11.0,
        "old_price_monthly_usd": 22.0,
        "price_yearly_usd": 9.0,
        "old_price_yearly_usd": 18.0,
        "popular": True,
        "first_month_half_price": True,
        "credits_per_month": 120000,
        "max_staff_seats": 1,
        "max_zones": 2,
        "retention_days": 30,
        "sla_tier": "99.9% Priority",
        "stripe_price_id_monthly": "price_1P9kIndCreatorMo",
        "stripe_price_id_yearly": "price_1P9kIndCreatorYr",
        "features": [
            "120,000 monthly processing credits",
            "Multi-engine cross-validation pipeline",
            "Instant SOS emergency dispatch trigger",
            "24/7 priority QA review escalation"
        ]
    },
    {
        "plan_id": "ind_pro",
        "workspace_type": "individual",
        "audience": "individual",
        "name": "Pro",
        "price_monthly_usd": 99.0,
        "price_yearly_usd": 82.0,
        "popular": False,
        "first_month_half_price": False,
        "credits_per_month": 600000,
        "max_staff_seats": 3,
        "max_zones": 5,
        "retention_days": 90,
        "sla_tier": "99.95% Premium",
        "stripe_price_id_monthly": "price_1P9kIndProMo",
        "stripe_price_id_yearly": "price_1P9kIndProYr",
        "features": [
            "600,000 monthly processing credits",
            "RTSP / WebRTC remote stream connector",
            "90-day cloud event archive & audit trail",
            "44.1 kHz forensic compliance PDF exports"
        ]
    },
    {
        "plan_id": "comp_starter",
        "workspace_type": "company",
        "audience": "company",
        "name": "Starter",
        "price_monthly_usd": 49.0,
        "price_yearly_usd": 39.0,
        "popular": False,
        "first_month_half_price": False,
        "credits_per_month": 250000,
        "max_staff_seats": 5,
        "max_zones": 5,
        "retention_days": 30,
        "sla_tier": "99.9% Business",
        "stripe_price_id_monthly": "price_1P9kCompStarterMo",
        "stripe_price_id_yearly": "price_1P9kCompStarterYr",
        "features": [
            "Up to 5 operator seats (SOC & Maintenance)",
            "5 active perimeter sensor zones",
            "250,000 monthly processing credits",
            "Standard tenant alert & escalation rules"
        ]
    },
    {
        "plan_id": "comp_creator",
        "workspace_type": "company",
        "audience": "company",
        "name": "Creator",
        "price_monthly_usd": 99.0,
        "old_price_monthly_usd": 198.0,
        "price_yearly_usd": 79.0,
        "old_price_yearly_usd": 158.0,
        "popular": True,
        "first_month_half_price": True,
        "credits_per_month": 1000000,
        "max_staff_seats": 25,
        "max_zones": 20,
        "retention_days": 180,
        "sla_tier": "99.95% Enterprise",
        "stripe_price_id_monthly": "price_1P9kCompCreatorMo",
        "stripe_price_id_yearly": "price_1P9kCompCreatorYr",
        "features": [
            "Up to 25 operator seats across all roles",
            "20 sensor zones + REST & Webhook API keys",
            "1,000,000 monthly processing credits",
            "Dedicated forensic QA review workbench"
        ]
    },
    {
        "plan_id": "comp_pro",
        "workspace_type": "company",
        "audience": "company",
        "name": "Pro",
        "price_monthly_usd": 299.0,
        "price_yearly_usd": 249.0,
        "popular": False,
        "first_month_half_price": False,
        "credits_per_month": 5000000,
        "max_staff_seats": 999,
        "max_zones": 999,
        "retention_days": 365,
        "sla_tier": "99.99% Mission Critical",
        "stripe_price_id_monthly": "price_1P9kCompProMo",
        "stripe_price_id_yearly": "price_1P9kCompProYr",
        "features": [
            "Unlimited operator seats & sensor zones",
            "Dedicated multi-site enterprise telemetry",
            "365-day compliance retention & SIEM export",
            "44.1 kHz lossless PCM API & 99.99% SLA"
        ]
    }
]


async def upgrade(db):
    """Applies Migration 002: Subscription Plans"""
    for plan in SUBSCRIPTION_PLANS:
        plan_doc = {**plan, "updated_at": datetime.utcnow()}
        await db.subscription_plans.update_one(
            {"plan_id": plan["plan_id"]},
            {"$set": plan_doc},
            upsert=True
        )

