"""
SonicSentinel AI - Enterprise Stripe Payment & Subscription Gateway Service
Handles Stripe Checkout Sessions, Webhooks, Customer Portal, and Local Sandbox Simulation.
"""
import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import stripe
from config.settings import settings
from src.security.quotas import normalize_plan, DEFAULT_INDIVIDUAL_PLAN, DEFAULT_COMPANY_PLAN

logger = logging.getLogger("SonicSentinel.StripeService")

# Setup Stripe API Key if provided
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def is_stripe_live() -> bool:
    """Returns True if a valid Stripe Secret Key is present in settings/environment."""
    key = settings.STRIPE_SECRET_KEY or os.getenv("STRIPE_SECRET_KEY", "")
    return bool(key and (key.startswith("sk_") or key.startswith("rk_")))


def get_stripe_publishable_key() -> str:
    """Returns publishable key or fallback sandbox key."""
    return settings.STRIPE_PUBLISHABLE_KEY or os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_sonicsentinel_sandbox")


async def create_checkout_session(
    db,
    plan_id: str,
    billing_cycle: str,
    user: Dict[str, Any],
    tenant_id: Optional[str] = None,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
    base_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Creates either a real Stripe Checkout Session or a clean Sandbox Checkout Session.
    """
    plan_doc = await db.subscription_plans.find_one({"plan_id": plan_id}, {"_id": 0}) if db is not None else None
    plan = normalize_plan(plan_doc)
    is_yearly = (billing_cycle or "monthly").lower() == "yearly"
    unit_price = plan["price_yearly"] if is_yearly else plan["price_monthly"]
    total_amount = round(unit_price * (12 if is_yearly else 1), 2)

    user_id = user.get("user_id", "")
    effective_tenant = tenant_id or user.get("tenant_id", "")
    user_email = user.get("email", "")

    # Live Stripe Integration
    if is_stripe_live():
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            line_item = {
                "price_data": {
                    "currency": settings.STRIPE_CURRENCY.lower(),
                    "product_data": {
                        "name": f"SonicSentinel AI - {plan['name']} ({plan['audience'].title()})",
                        "description": plan.get("description", "Enterprise Acoustic Threat Intelligence"),
                    },
                    "unit_amount": int(round(unit_price * 100)),
                    "recurring": {"interval": "year" if is_yearly else "month"}
                },
                "quantity": 1
            }

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                customer_email=user_email if "@" in user_email else None,
                line_items=[line_item],
                metadata={
                    "plan_id": plan_id,
                    "user_id": user_id,
                    "tenant_id": effective_tenant,
                    "billing_cycle": "yearly" if is_yearly else "monthly"
                },
                success_url=success_url or f"{base_url}/app/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url or f"{base_url}/pricing?status=cancelled"
            )
            logger.info(f"Created Stripe Live Checkout Session {session.id} for plan {plan_id}")
            return {
                "status": "success",
                "mode": "stripe_live",
                "checkout_url": session.url,
                "session_id": session.id,
                "amount": total_amount,
                "plan": plan
            }
        except Exception as exc:
            logger.warning(f"Stripe live checkout session creation notice: {exc}. Falling back to sandbox simulator.")

    # Seamless Sandbox Simulation
    session_id = f"cs_sandbox_{uuid.uuid4().hex[:12]}"
    session_doc = {
        "session_id": session_id,
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "audience": plan["audience"],
        "billing_cycle": "yearly" if is_yearly else "monthly",
        "unit_price": unit_price,
        "total_amount": total_amount,
        "currency": settings.STRIPE_CURRENCY.upper(),
        "user_id": user_id,
        "user_email": user_email,
        "tenant_id": effective_tenant,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=2)).isoformat()
    }

    if db is not None:
        await db.checkout_sessions.insert_one(session_doc)

    return {
        "status": "success",
        "mode": "sandbox",
        "checkout_url": f"/api/stripe/sandbox-checkout?session_id={session_id}",
        "session_id": session_id,
        "amount": total_amount,
        "plan": plan
    }


async def apply_subscription_activation(
    db,
    plan_id: str,
    billing_cycle: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    stripe_customer_id: str = "",
    stripe_sub_id: str = "",
    payment_method: str = "Stripe Card"
) -> Dict[str, Any]:
    """
    Activates or updates the subscription status and plan in MongoDB for the target entity.
    """
    if db is None:
        return {"status": "error", "message": "Database disconnected"}

    plan_doc = await db.subscription_plans.find_one({"plan_id": plan_id}, {"_id": 0})
    plan = normalize_plan(plan_doc)
    is_yearly = (billing_cycle or "monthly").lower() == "yearly"
    renewal_days = 365 if is_yearly else 30
    renewal_date = (datetime.utcnow() + timedelta(days=renewal_days)).strftime("%b %d, %Y")

    is_company = tenant_id and tenant_id not in ("platform_global", "b2c_residents")

    if is_company:
        update_doc = {
            "plan_id": plan_id,
            "plan_tier": plan_id.replace("comp_", ""),
            "subscription_status": "active",
            "billing_cycle": "yearly" if is_yearly else "monthly",
            "renewal_date": renewal_date,
            "stripe_customer_id": stripe_customer_id or f"cus_{uuid.uuid4().hex[:8]}",
            "stripe_subscription_id": stripe_sub_id or f"sub_{uuid.uuid4().hex[:8]}",
            "payment_method": payment_method,
            "credits_used": 0,
            "usage_month": datetime.utcnow().strftime("%Y-%m"),
            "updated_at": datetime.utcnow().isoformat()
        }
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": update_doc})

        # Insert audit log
        await db.audit_logs.insert_one({
            "log_id": f"LOG-SUB-{uuid.uuid4().hex[:6].upper()}",
            "tenant_id": tenant_id,
            "user_id": user_id or "system",
            "username": "Subscription Engine",
            "role": "billing",
            "action": "Subscription Activated",
            "details": f"Company upgraded to {plan['name']} ({billing_cycle}) via {payment_method}.",
            "status": "Success",
            "is_anomaly": False,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        })
        return {"status": "success", "entity": "tenant", "tenant_id": tenant_id, "plan": plan}
    else:
        # Individual User
        update_doc = {
            "plan_id": plan_id,
            "plan_tier": plan_id.replace("ind_", ""),
            "subscription_status": "active",
            "billing_cycle": "yearly" if is_yearly else "monthly",
            "renewal_date": renewal_date,
            "stripe_customer_id": stripe_customer_id or f"cus_{uuid.uuid4().hex[:8]}",
            "stripe_subscription_id": stripe_sub_id or f"sub_{uuid.uuid4().hex[:8]}",
            "payment_method": payment_method,
            "credits_used": 0,
            "usage_month": datetime.utcnow().strftime("%Y-%m"),
            "updated_at": datetime.utcnow().isoformat()
        }
        await db.users.update_one({"user_id": user_id}, {"$set": update_doc})

        await db.audit_logs.insert_one({
            "log_id": f"LOG-SUB-{uuid.uuid4().hex[:6].upper()}",
            "tenant_id": "b2c_residents",
            "user_id": user_id or "system",
            "username": "Subscription Engine",
            "role": "billing",
            "action": "Individual Subscription Activated",
            "details": f"User upgraded to {plan['name']} ({billing_cycle}) via {payment_method}.",
            "status": "Success",
            "is_anomaly": False,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        })
        return {"status": "success", "entity": "user", "user_id": user_id, "plan": plan}


async def process_webhook_event(db, payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Parses and handles Stripe Webhook events.
    """
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET or os.getenv("STRIPE_WEBHOOK_SECRET", "")
    event = None

    if webhook_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as exc:
            logger.error(f"Stripe Webhook signature verification error: {exc}")
            return {"status": "error", "message": f"Webhook signature failed: {exc}"}
    else:
        try:
            event = json.loads(payload.decode("utf-8"))
        except Exception as exc:
            return {"status": "error", "message": f"Invalid JSON payload: {exc}"}

    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})
    logger.info(f"Received Stripe Webhook event: {event_type}")

    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {})
        plan_id = metadata.get("plan_id", "comp_starter")
        billing_cycle = metadata.get("billing_cycle", "monthly")
        user_id = metadata.get("user_id")
        tenant_id = metadata.get("tenant_id")
        cust_id = data_object.get("customer", "")
        sub_id = data_object.get("subscription", "")

        return await apply_subscription_activation(
            db,
            plan_id=plan_id,
            billing_cycle=billing_cycle,
            user_id=user_id,
            tenant_id=tenant_id,
            stripe_customer_id=cust_id,
            stripe_sub_id=sub_id,
            payment_method="Stripe Checkout"
        )

    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        cust_id = data_object.get("customer", "")
        sub_id = data_object.get("id", "")
        if db is not None:
            await db.tenants.update_many(
                {"$or": [{"stripe_customer_id": cust_id}, {"stripe_subscription_id": sub_id}]},
                {"$set": {"subscription_status": "cancelled", "updated_at": datetime.utcnow().isoformat()}}
            )
            await db.users.update_many(
                {"$or": [{"stripe_customer_id": cust_id}, {"stripe_subscription_id": sub_id}]},
                {"$set": {"subscription_status": "cancelled", "updated_at": datetime.utcnow().isoformat()}}
            )
        return {"status": "processed", "event": event_type}

    elif event_type == "invoice.payment_failed":
        cust_id = data_object.get("customer", "")
        if db is not None:
            await db.tenants.update_many(
                {"stripe_customer_id": cust_id},
                {"$set": {"subscription_status": "past_due", "updated_at": datetime.utcnow().isoformat()}}
            )
            await db.users.update_many(
                {"stripe_customer_id": cust_id},
                {"$set": {"subscription_status": "past_due", "updated_at": datetime.utcnow().isoformat()}}
            )
        return {"status": "processed", "event": event_type}

    return {"status": "ignored", "event": event_type}


async def create_customer_portal(db, user: Dict[str, Any], tenant_id: Optional[str] = None, return_url: str = "/app") -> str:
    """
    Creates a Stripe Customer Portal session or returns fallback link to subscription settings.
    """
    effective_tenant = tenant_id or user.get("tenant_id")
    cust_id = ""

    if db is not None:
        if effective_tenant and effective_tenant not in ("platform_global", "b2c_residents"):
            tenant = await db.tenants.find_one({"tenant_id": effective_tenant})
            cust_id = (tenant or {}).get("stripe_customer_id", "")
        else:
            user_doc = await db.users.find_one({"user_id": user.get("user_id")})
            cust_id = (user_doc or {}).get("stripe_customer_id", "")

    if is_stripe_live() and cust_id and not cust_id.startswith("cus_sandbox"):
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            portal_session = stripe.billing_portal.Session.create(
                customer=cust_id,
                return_url=return_url
            )
            return portal_session.url
        except Exception as exc:
            logger.warning(f"Stripe portal creation notice: {exc}")

    return "/app/admin/subscriptions" if user.get("role") in ("super_admin", "administrator") else "/app/profile"
