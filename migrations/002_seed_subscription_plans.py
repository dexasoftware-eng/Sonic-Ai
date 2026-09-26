"""
Migration 002: Seed Subscription Plans (Individual & Enterprise Tiers)
Populates `subscription_plans` collection in MongoDB.
"""
from datetime import datetime

SUBSCRIPTION_PLANS = [
    {
        "plan_id": "ind_starter",
        "workspace_type": "individual",
        "name": "Starter",
        "price_monthly_usd": 6.0,
        "price_yearly_usd": 5.0,
        "popular": False,
        "first_month_half_price": False,
        "credits_per_month": 30000,
        "features": [
            "30k acoustic credits/month",
            "All 10 Core Sound Classes",
            "Live Microphone & File Upload"
        ]
    },
    {
        "plan_id": "ind_creator",
        "workspace_type": "individual",
        "name": "Creator",
        "price_monthly_usd": 11.0,
        "old_price_monthly_usd": 22.0,
        "price_yearly_usd": 9.0,
        "old_price_yearly_usd": 18.0,
        "popular": True,
        "first_month_half_price": True,
        "credits_per_month": 121000,
        "features": [
            "121k acoustic credits/month",
            "Dual-AI (Python + GTM) Consensus",
            "Instant SOS Help Phrase Trigger",
            "Global Platform Reviewer Support"
        ]
    },
    {
        "plan_id": "ind_pro",
        "workspace_type": "individual",
        "name": "Pro",
        "price_monthly_usd": 99.0,
        "price_yearly_usd": 82.0,
        "popular": False,
        "first_month_half_price": False,
        "credits_per_month": 600000,
        "features": [
            "600k acoustic credits/month",
            "Remote Stream URL Connector",
            "Everything in Creator",
            "44.1 kHz Forensic PDF Reports"
        ]
    },
    {
        "plan_id": "comp_starter",
        "workspace_type": "company",
        "name": "Starter",
        "price_monthly_usd": 49.0,
        "price_yearly_usd": 39.0,
        "popular": False,
        "first_month_half_price": False,
        "max_staff_seats": 5,
        "max_zones": 5,
        "features": [
            "Up to 5 Staff Seats (SOC & Maint)",
            "5 Acoustic Sensor Zones",
            "Standard Tenant Alert Rules"
        ]
    },
    {
        "plan_id": "comp_creator",
        "workspace_type": "company",
        "name": "Creator",
        "price_monthly_usd": 99.0,
        "old_price_monthly_usd": 198.0,
        "price_yearly_usd": 79.0,
        "old_price_yearly_usd": 158.0,
        "popular": True,
        "first_month_half_price": True,
        "max_staff_seats": 25,
        "max_zones": 20,
        "features": [
            "Up to 25 Staff Seats (All 4 Roles)",
            "20 Acoustic Zones + IoT API Keys",
            "Custom Class Live Model Retraining",
            "Company Forensic Review Queue"
        ]
    },
    {
        "plan_id": "comp_pro",
        "workspace_type": "company",
        "name": "Pro",
        "price_monthly_usd": 299.0,
        "price_yearly_usd": 249.0,
        "popular": False,
        "first_month_half_price": False,
        "max_staff_seats": 999,
        "max_zones": 999,
        "features": [
            "Unlimited Staff Seats & Zones",
            "Dedicated Custom AI Studio",
            "Everything in Creator",
            "44.1 kHz PCM Audio via API & SLA"
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
