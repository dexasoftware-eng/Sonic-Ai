"""
Detectra AI - Subscription Quotas & Security Enforcement Engine
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("Detectra.Quotas")

# Default fallback tier configurations
DEFAULT_INDIVIDUAL_PLAN = {
    "plan_id": "ind_starter",
    "name": "Starter",
    "audience": "individual",
    "workspace_type": "individual",
    "price_monthly": 6.0,
    "price_yearly": 5.0,
    "credits_per_month": 30000,
    "max_staff_seats": 1,
    "max_zones": 1,
    "features": ["30k acoustic credits/month", "Core 10 Sound Classes", "Live Microphone & File Upload"],
    "is_active": True
}

DEFAULT_COMPANY_PLAN = {
    "plan_id": "comp_starter",
    "name": "Starter",
    "audience": "company",
    "workspace_type": "company",
    "price_monthly": 49.0,
    "price_yearly": 39.0,
    "credits_per_month": 250000,
    "max_staff_seats": 5,
    "max_zones": 5,
    "features": ["Up to 5 Staff Seats", "5 Acoustic Zones", "Standard Alert Rules"],
    "is_active": True
}


def normalize_plan(p: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalizes subscription plan attributes into consistent schema."""
    if not p:
        return dict(DEFAULT_INDIVIDUAL_PLAN)

    plan = dict(p)
    plan_id = str(plan.get("plan_id") or "plan_custom")
    name = str(plan.get("name") or "Custom Tier")
    audience = str(plan.get("workspace_type") or plan.get("audience") or ("company" if plan_id.startswith("comp") else "individual")).lower()
    
    price_monthly = float(plan.get("price_monthly") or plan.get("price_monthly_usd") or 0.0)
    price_yearly = float(plan.get("price_yearly") or plan.get("price_yearly_usd") or price_monthly)
    old_price_monthly = plan.get("old_price_monthly") or plan.get("old_price_monthly_usd")
    old_price_yearly = plan.get("old_price_yearly") or plan.get("old_price_yearly_usd")

    credits_limit = int(plan.get("credits_per_month") or plan.get("credits_limit") or (250000 if audience == "company" else 30000))
    max_seats = int(plan.get("max_staff_seats") or (25 if "creator" in plan_id else (999 if "pro" in plan_id else 5)))
    max_zones = int(plan.get("max_zones") or plan.get("sensors_limit") or (20 if "creator" in plan_id else (999 if "pro" in plan_id else 5)))

    features = plan.get("features") or []
    if isinstance(features, str):
        features = [f.strip() for f in features.split("\n") if f.strip()]

    retention_days = int(plan.get("retention_days") or (365 if "pro" in plan_id else (180 if "creator" in plan_id else 30)))
    sla_tier = str(plan.get("sla_tier") or ("99.99% Mission Critical" if "pro" in plan_id else ("99.95% Enterprise" if "creator" in plan_id else "99.9% Standard")))

    return {
        "plan_id": plan_id,
        "name": name,
        "audience": audience,
        "workspace_type": audience,
        "description": plan.get("description") or f"Enterprise {name} Tier for {audience.title()} operations.",
        "badge": plan.get("badge") or ("Most Popular" if plan.get("popular") else ""),
        "popular": bool(plan.get("popular", False)),
        "first_month_half_price": bool(plan.get("first_month_half_price", False)),
        "price_monthly": price_monthly,
        "price_yearly": price_yearly,
        "old_price_monthly": float(old_price_monthly) if old_price_monthly is not None else None,
        "old_price_yearly": float(old_price_yearly) if old_price_yearly is not None else None,
        "credits_per_month": credits_limit,
        "credits_limit": credits_limit,
        "credits_label": plan.get("credits_label") or f"{int(credits_limit/1000):,}k credits/mo",
        "max_staff_seats": max_seats,
        "max_zones": max_zones,
        "sensors_limit": max_zones,
        "retention_days": retention_days,
        "sla_tier": sla_tier,
        "features": list(features),
        "stripe_price_id_monthly": plan.get("stripe_price_id_monthly") or f"price_1P9k{plan_id.title().replace('_', '')}Mo",
        "stripe_price_id_yearly": plan.get("stripe_price_id_yearly") or f"price_1P9k{plan_id.title().replace('_', '')}Yr",
        "is_active": plan.get("is_active", True)
    }


async def get_entity_plan(db, tenant_id: Optional[str] = None, user_id: Optional[str] = None, user_role: Optional[str] = None) -> Dict[str, Any]:
    """Resolves active subscription plan for a tenant company or individual user."""
    if db is None:
        return normalize_plan(DEFAULT_INDIVIDUAL_PLAN)

    # Super Admins operate on unlimited platform tier
    if user_role in ("super_admin", "administrator"):
        return {
            "plan_id": "platform_unlimited",
            "name": "Super Admin Master",
            "audience": "company",
            "workspace_type": "company",
            "price_monthly": 0.0,
            "price_yearly": 0.0,
            "credits_per_month": 999999999,
            "credits_limit": 999999999,
            "max_staff_seats": 99999,
            "max_zones": 99999,
            "features": ["Unlimited Global Platform Access", "Master Security Privilege"],
            "is_active": True
        }

    # Company Tenant check
    if tenant_id and tenant_id not in ("platform_global", "b2c_residents"):
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if tenant:
            plan_key = tenant.get("plan_id") or tenant.get("plan_tier") or "comp_starter"
            # Map legacy names (starter -> comp_starter, creator -> comp_creator)
            if not plan_key.startswith("comp_") and not plan_key.startswith("ind_"):
                plan_key = f"comp_{plan_key}"

            plan_doc = await db.subscription_plans.find_one(
                {"$or": [{"plan_id": plan_key}, {"plan_id": plan_key.replace("comp_", "")}]},
                {"_id": 0}
            )
            if plan_doc:
                normalized = normalize_plan(plan_doc)
                # Apply custom overrides if stored on tenant
                if tenant.get("custom_max_seats"):
                    normalized["max_staff_seats"] = int(tenant["custom_max_seats"])
                if tenant.get("custom_max_zones"):
                    normalized["max_zones"] = int(tenant["custom_max_zones"])
                return normalized
        return normalize_plan(DEFAULT_COMPANY_PLAN)

    # Individual User check
    if user_id:
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if user:
            plan_key = user.get("plan_id") or user.get("plan_tier") or "ind_starter"
            if not plan_key.startswith("ind_") and not plan_key.startswith("comp_"):
                plan_key = f"ind_{plan_key}"

            plan_doc = await db.subscription_plans.find_one(
                {"$or": [{"plan_id": plan_key}, {"plan_id": plan_key.replace("ind_", "")}]},
                {"_id": 0}
            )
            if plan_doc:
                return normalize_plan(plan_doc)

    return normalize_plan(DEFAULT_INDIVIDUAL_PLAN)


async def check_audio_quota(db, user: Dict[str, Any], cost: int = 1) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Security Policy: Verifies if the entity has sufficient acoustic credits.
    Returns: (is_allowed, error_message, quota_details)
    """
    role = user.get("role", "normal_user")
    if role in ("super_admin", "administrator"):
        return True, "", {"unlimited": True, "credits_remaining": 999999999}

    if db is None:
        return True, "", {"credits_remaining": 10000}

    tenant_id = user.get("tenant_id")
    user_id = user.get("user_id")
    plan = await get_entity_plan(db, tenant_id=tenant_id, user_id=user_id, user_role=role)
    limit = plan["credits_per_month"]

    # Determine usage tracker
    is_company = tenant_id and tenant_id not in ("platform_global", "b2c_residents")
    now_month = datetime.utcnow().strftime("%Y-%m")

    if is_company:
        tenant = await db.tenants.find_one({"tenant_id": tenant_id})
        # Check if subscription status is active
        sub_status = (tenant.get("subscription_status") if tenant else None) or "active"
        if sub_status in ("suspended", "cancelled", "past_due"):
            return False, f"Company subscription is currently '{sub_status}'. Audio inference is temporarily disabled.", {
                "status": sub_status, "limit": limit
            }

        usage_month = (tenant.get("usage_month") if tenant else None) or now_month
        raw_credits = (tenant.get("credits_used") if tenant else 0) if usage_month == now_month else 0
        credits_used = int(raw_credits or 0)
        limit = int(limit or 250000)

        if credits_used + cost > limit:
            return False, (
                f"Monthly acoustic credit quota exceeded ({credits_used:,} / {limit:,} used). "
                f"Your organization '{(tenant.get('name') if tenant else None) or 'Tenant'}' needs to upgrade its subscription plan to continue processing audio."
            ), {
                "credits_used": credits_used,
                "credits_limit": limit,
                "plan_name": plan["name"],
                "upgrade_required": True
            }

        # Track usage safely with $set so null fields in MongoDB never fail
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "usage_month": now_month,
                    "credits_used": credits_used + cost
                }
            }
        )
        return True, "", {
            "credits_used": credits_used + cost,
            "credits_limit": limit,
            "credits_remaining": max(0, limit - (credits_used + cost)),
            "plan_name": plan["name"]
        }
    else:
        # Individual B2C user
        user_doc = await db.users.find_one({"user_id": user_id}) if user_id else None
        sub_status = (user_doc.get("subscription_status") if user_doc else None) or "active"
        if sub_status in ("suspended", "cancelled", "past_due"):
            return False, f"Your subscription is currently '{sub_status}'. Inference is locked.", {"status": sub_status}

        usage_month = (user_doc.get("usage_month") if user_doc else None) or now_month
        raw_credits = (user_doc.get("credits_used") if user_doc else 0) if usage_month == now_month else 0
        credits_used = int(raw_credits or 0)
        limit = int(limit or 30000)

        if credits_used + cost > limit:
            return False, (
                f"Monthly acoustic credit quota exceeded ({credits_used:,} / {limit:,} used). "
                f"Please upgrade to Creator or Pro tier to get more acoustic inference credits."
            ), {
                "credits_used": credits_used,
                "credits_limit": limit,
                "plan_name": plan["name"],
                "upgrade_required": True
            }

        if user_id:
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "usage_month": now_month,
                        "credits_used": credits_used + cost
                    }
                }
            )
        return True, "", {
            "credits_used": credits_used + cost,
            "credits_limit": limit,
            "credits_remaining": max(0, limit - (credits_used + cost)),
            "plan_name": plan["name"]
        }


async def check_staff_seat_limit(db, tenant_id: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Security Policy: Verifies if tenant company has available staff seats.
    """
    if not tenant_id or tenant_id in ("platform_global", "b2c_residents"):
        return True, "", {"unlimited": True}

    if db is None:
        return True, "", {"seats_allowed": 999}

    plan = await get_entity_plan(db, tenant_id=tenant_id)
    max_seats = plan["max_staff_seats"]

    current_seats = await db.users.count_documents({
        "tenant_id": tenant_id,
        "status": {"$ne": "deactivated"}
    })

    if current_seats >= max_seats:
        return False, (
            f"Staff seat limit reached ({current_seats} of {max_seats} seats used). "
            f"Your current plan '{plan['name']}' allows up to {max_seats} team members. "
            f"Upgrade to Creator or Pro to invite additional security operators and engineers."
        ), {
            "current_seats": current_seats,
            "max_seats": max_seats,
            "plan_name": plan["name"],
            "upgrade_required": True
        }

    return True, "", {
        "current_seats": current_seats,
        "max_seats": max_seats,
        "seats_remaining": max_seats - current_seats,
        "plan_name": plan["name"]
    }


async def check_zone_limit(db, tenant_id: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Security Policy: Verifies if tenant company has available sensor zone quotas.
    """
    if not tenant_id or tenant_id in ("platform_global", "b2c_residents"):
        return True, "", {"unlimited": True}

    if db is None:
        return True, "", {"zones_allowed": 999}

    plan = await get_entity_plan(db, tenant_id=tenant_id)
    max_zones = plan["max_zones"]

    # Count registered sensors/zones for this tenant
    current_zones = await db.sensors.count_documents({
        "tenant_id": tenant_id,
        "status": {"$ne": "retired"}
    })

    if current_zones >= max_zones:
        return False, (
            f"Sensor zone limit reached ({current_zones} of {max_zones} zones active). "
            f"Your organization's '{plan['name']}' plan supports a maximum of {max_zones} zones. "
            f"Upgrade your subscription to provision additional monitoring zones."
        ), {
            "current_zones": current_zones,
            "max_zones": max_zones,
            "plan_name": plan["name"],
            "upgrade_required": True
        }

    return True, "", {
        "current_zones": current_zones,
        "max_zones": max_zones,
        "zones_remaining": max_zones - current_zones,
        "plan_name": plan["name"]
    }


async def get_subscription_usage_summary(db, tenant_id: Optional[str] = None, user_id: Optional[str] = None, user_role: Optional[str] = None) -> Dict[str, Any]:
    """Generates comprehensive quota and subscription metrics for display."""
    plan = await get_entity_plan(db, tenant_id=tenant_id, user_id=user_id, user_role=user_role)
    now_month = datetime.utcnow().strftime("%Y-%m")

    is_company = tenant_id and tenant_id not in ("platform_global", "b2c_residents")
    if is_company and db is not None:
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}) or {}
        usage_month = tenant.get("usage_month") or now_month
        credits_used = tenant.get("credits_used", 0) if usage_month == now_month else 0
        current_seats = await db.users.count_documents({"tenant_id": tenant_id, "status": {"$ne": "deactivated"}})
        current_zones = await db.sensors.count_documents({"tenant_id": tenant_id, "status": {"$ne": "retired"}})

        return {
            "plan": plan,
            "subscription_status": tenant.get("subscription_status", "active"),
            "billing_cycle": tenant.get("billing_cycle", "monthly"),
            "renewal_date": tenant.get("renewal_date") or (datetime.utcnow().replace(day=28).strftime("%b %d, %Y")),
            "stripe_customer_id": tenant.get("stripe_customer_id", ""),
            "stripe_subscription_id": tenant.get("stripe_subscription_id", ""),
            "credits_used": credits_used,
            "credits_limit": plan["credits_per_month"],
            "credits_percent": min(100.0, round((credits_used / max(1, plan["credits_per_month"])) * 100, 1)),
            "seats_used": current_seats,
            "seats_limit": plan["max_staff_seats"],
            "seats_percent": min(100.0, round((current_seats / max(1, plan["max_staff_seats"])) * 100, 1)),
            "zones_used": current_zones,
            "zones_limit": plan["max_zones"],
            "zones_percent": min(100.0, round((current_zones / max(1, plan["max_zones"])) * 100, 1)),
        }
    elif user_id and db is not None:
        user_doc = await db.users.find_one({"user_id": user_id}) or {}
        usage_month = user_doc.get("usage_month") or now_month
        credits_used = user_doc.get("credits_used", 0) if usage_month == now_month else 0
        return {
            "plan": plan,
            "subscription_status": user_doc.get("subscription_status", "active"),
            "billing_cycle": user_doc.get("billing_cycle", "monthly"),
            "renewal_date": user_doc.get("renewal_date") or (datetime.utcnow().replace(day=28).strftime("%b %d, %Y")),
            "stripe_customer_id": user_doc.get("stripe_customer_id", ""),
            "stripe_subscription_id": user_doc.get("stripe_subscription_id", ""),
            "credits_used": credits_used,
            "credits_limit": plan["credits_per_month"],
            "credits_percent": min(100.0, round((credits_used / max(1, plan["credits_per_month"])) * 100, 1)),
            "seats_used": 1,
            "seats_limit": 1,
            "seats_percent": 100.0,
            "zones_used": 1,
            "zones_limit": 1,
            "zones_percent": 100.0,
        }

    return {
        "plan": plan,
        "subscription_status": "active",
        "billing_cycle": "monthly",
        "renewal_date": "N/A",
        "credits_used": 0,
        "credits_limit": plan["credits_per_month"],
        "credits_percent": 0.0,
        "seats_used": 1,
        "seats_limit": plan["max_staff_seats"],
        "seats_percent": 10.0,
        "zones_used": 1,
        "zones_limit": plan["max_zones"],
        "zones_percent": 10.0
    }
