"""
SonicSentinel AI - Stripe Billing & Subscription Routing
Endpoints for Checkout Sessions, Webhooks, Customer Portal, and Interactive Sandbox Flow.
"""
import uuid
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.mongodb import ensure_database
from src.app.app_routes import get_authenticated_user
from src.security.quotas import normalize_plan
from src.services.stripe_service import (
    is_stripe_live, get_stripe_publishable_key,
    create_checkout_session, apply_subscription_activation,
    process_webhook_event, create_customer_portal
)

logger = logging.getLogger("SonicSentinel.StripeRouter")
stripe_router = APIRouter(prefix="/api/stripe", tags=["Stripe Billing"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))


@stripe_router.get("/config")
async def get_stripe_configuration():
    """Returns public Stripe configuration status."""
    return {
        "is_live": is_stripe_live(),
        "publishable_key": get_stripe_publishable_key(),
        "currency": settings.STRIPE_CURRENCY.upper()
    }


@stripe_router.post("/create-checkout-session")
async def route_create_checkout_session(request: Request):
    """
    Creates a Stripe Checkout Session or Sandbox Checkout Session for a plan.
    """
    db = await ensure_database()
    body = await request.json()
    plan_id = body.get("plan_id")
    billing_cycle = body.get("billing_cycle", "monthly")
    tenant_id = body.get("tenant_id")
    success_url = body.get("success_url")
    cancel_url = body.get("cancel_url")

    if not plan_id:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Missing required 'plan_id'."})

    # Retrieve current user session or fallback for onboarding
    user = await get_authenticated_user(request)
    if not user:
        # Check if email passed in body for pre-registration
        guest_email = body.get("email") or "customer@sonicsentinel.ai"
        user = {
            "user_id": body.get("user_id") or f"USR-TEMP-{uuid.uuid4().hex[:6].upper()}",
            "email": guest_email,
            "tenant_id": tenant_id or "b2c_residents",
            "role": "normal_user"
        }

    base_url = str(request.base_url).rstrip("/")
    result = await create_checkout_session(
        db=db,
        plan_id=plan_id,
        billing_cycle=billing_cycle,
        user=user,
        tenant_id=tenant_id or user.get("tenant_id"),
        success_url=success_url,
        cancel_url=cancel_url,
        base_url=base_url
    )
    return result


@stripe_router.post("/webhook")
async def route_stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    """Receives and processes asynchronous Stripe Webhook callbacks."""
    db = await ensure_database()
    payload = await request.body()
    res = await process_webhook_event(db, payload=payload, sig_header=stripe_signature or "")
    status_code = 400 if res.get("status") == "error" else 200
    return JSONResponse(status_code=status_code, content=res)


@stripe_router.get("/customer-portal")
async def route_customer_portal(request: Request):
    """Generates customer billing portal redirect URL."""
    db = await ensure_database()
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)

    portal_url = await create_customer_portal(db, user=user)
    return RedirectResponse(url=portal_url, status_code=302)


@stripe_router.get("/sandbox-checkout", response_class=HTMLResponse)
async def serve_sandbox_checkout(request: Request, session_id: str):
    """
    Interactive Stripe Checkout Sandbox UI matching enterprise dark mode theme.
    """
    db = await ensure_database()
    session = await db.checkout_sessions.find_one({"session_id": session_id}, {"_id": 0}) if db is not None else None
    if not session:
        return HTMLResponse("<h3>Invalid or expired checkout session.</h3>", status_code=404)

    plan_doc = await db.subscription_plans.find_one({"plan_id": session.get("plan_id")}, {"_id": 0}) if db is not None else None
    plan = normalize_plan(plan_doc)

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Stripe Checkout — SonicSentinel AI</title>
      <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
      <style>
        :root {{
          --bg-dark: #090a10;
          --card-bg: #12131d;
          --border: #232536;
          --accent: #6366f1;
          --accent-purple: #8b5cf6;
          --text: #f4f4f5;
          --text-muted: #9ca3af;
        }}
        * {{ box-sizing: border-box; margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: var(--bg-dark); color: var(--text); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .checkout-box {{
          width: 100%; max-width: 900px; background: var(--card-bg); border: 1px solid var(--border);
          border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); overflow: hidden; display: grid; grid-template-columns: 1fr 1.1fr;
        }}
        @media(max-width: 768px) {{ .checkout-box {{ grid-template-columns: 1fr; }} }}
        .summary-pane {{ background: #0c0d16; padding: 40px; border-right: 1px solid var(--border); display: flex; flex-direction: column; justify-content: space-between; }}
        .brand-logo {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 18px; color: #fff; margin-bottom: 30px; }}
        .brand-badge {{ background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); font-size: 11px; padding: 2px 8px; border-radius: 999px; text-transform: uppercase; }}
        .plan-title {{ font-size: 26px; font-weight: 600; margin-bottom: 8px; }}
        .plan-price {{ font-size: 44px; font-weight: 700; color: #fff; display: flex; align-items: baseline; gap: 6px; margin: 20px 0; }}
        .plan-price span {{ font-size: 16px; color: var(--text-muted); font-weight: 400; }}
        .features-list {{ list-style: none; margin-top: 20px; display: flex; flex-direction: column; gap: 12px; }}
        .features-list li {{ display: flex; align-items: center; gap: 10px; color: #d1d5db; font-size: 14px; }}
        .features-list li i {{ color: #10b981; font-size: 12px; }}
        .payment-pane {{ padding: 40px; }}
        .pane-heading {{ font-size: 18px; font-weight: 600; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; }}
        .stripe-pill {{ display: inline-flex; align-items: center; gap: 6px; background: #635bff; color: white; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
        .form-group {{ margin-bottom: 18px; }}
        .form-label {{ display: block; font-size: 12px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; letter-spacing: 0.5px; font-weight: 600; }}
        .form-input {{ width: 100%; background: #181926; border: 1px solid #2a2d42; color: #fff; padding: 12px 14px; border-radius: 8px; font-size: 14px; outline: none; transition: 0.2s border; }}
        .form-input:focus {{ border-color: var(--accent); }}
        .row-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        .submit-btn {{
          width: 100%; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: #fff; border: none; padding: 15px; border-radius: 8px;
          font-weight: 600; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 24px; transition: opacity 0.2s;
        }}
        .submit-btn:hover {{ opacity: 0.95; }}
        .guarantee {{ text-align: center; color: var(--text-muted); font-size: 12px; margin-top: 16px; display: flex; align-items: center; justify-content: center; gap: 6px; }}
      </style>
    </head>
    <body>
      <div class="checkout-box">
        <div class="summary-pane">
          <div>
            <div class="brand-logo">
              <i class="fa-solid fa-waveform-lines" style="color: #6366f1;"></i>
              <span>SonicSentinel AI</span>
              <span class="brand-badge">Stripe Gateway</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Subscribe To Plan</div>
            <div class="plan-title">{plan['name']} Tier</div>
            <div style="color: var(--text-muted); font-size: 13px;">{session.get('audience', 'Enterprise').title()} Safety & Threat Intelligence Workspace</div>
            
            <div class="plan-price">
              ${session.get('total_amount', 0):,.2f}
              <span>/{'year' if session.get('billing_cycle') == 'yearly' else 'month'}</span>
            </div>

            <ul class="features-list">
              {''.join(f'<li><i class="fa-solid fa-check"></i><span>{f}</span></li>' for f in plan['features'])}
            </ul>
          </div>

          <div style="font-size: 12px; color: #6b7280; border-top: 1px solid var(--border); padding-top: 20px; margin-top: 30px;">
            Secure 256-bit TLS encrypted session &bull; Instant activation
          </div>
        </div>

        <div class="payment-pane">
          <div class="pane-heading">
            <span>Payment Details</span>
            <div class="stripe-pill"><i class="fa-brands fa-stripe" style="font-size: 16px;"></i> Sandbox Mode</div>
          </div>

          <form action="/api/stripe/sandbox-confirm" method="POST">
            <input type="hidden" name="session_id" value="{session_id}">
            
            <div class="form-group">
              <label class="form-label">Email Address</label>
              <input type="email" class="form-input" name="email" value="{session.get('user_email', 'admin@sonicsentinel.ai')}" required>
            </div>

            <div class="form-group">
              <label class="form-label">Card Information</label>
              <div style="position: relative;">
                <input type="text" class="form-input" name="card_number" value="4242 &bull;&bull;&bull;&bull; &bull;&bull;&bull;&bull; 4242" readonly style="letter-spacing: 1px;">
                <i class="fa-brands fa-cc-visa" style="position: absolute; right: 14px; top: 14px; font-size: 18px; color: #818cf8;"></i>
              </div>
            </div>

            <div class="row-2">
              <div class="form-group">
                <label class="form-label">Expiration</label>
                <input type="text" class="form-input" value="12 / 28" readonly>
              </div>
              <div class="form-group">
                <label class="form-label">CVC</label>
                <input type="text" class="form-input" value="888" readonly>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Cardholder Name</label>
              <input type="text" class="form-input" name="cardholder_name" value="Verified Account Holder" required>
            </div>

            <div class="form-group">
              <label class="form-label">Country / Region</label>
              <select class="form-input" style="cursor: pointer;">
                <option selected>United States (USD)</option>
                <option>United Kingdom (GBP)</option>
                <option>European Union (EUR)</option>
                <option>Canada (CAD)</option>
                <option>Global (International)</option>
              </select>
            </div>

            <button type="submit" class="submit-btn">
              <i class="fa-solid fa-lock"></i>
              <span>Activate {plan['name']} Subscription (${session.get('total_amount', 0):,.2f})</span>
            </button>

            <div class="guarantee">
              <i class="fa-solid fa-shield-check" style="color: #10b981;"></i>
              <span>Auto-renews {'yearly' if session.get('billing_cycle') == 'yearly' else 'monthly'}. Cancel anytime in 1-click.</span>
            </div>
          </form>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


@stripe_router.post("/sandbox-confirm")
@stripe_router.get("/sandbox-confirm")
async def route_sandbox_confirm(request: Request, session_id: Optional[str] = None):
    """Processes sandbox payment confirmation and activates subscription."""
    if not session_id:
        try:
            form = await request.form()
            session_id = form.get("session_id")
        except Exception:
            pass
    if not session_id:
        session_id = request.query_params.get("session_id")
    db = await ensure_database()

    if db is None or not session_id:
        return RedirectResponse(url="/pricing?status=error", status_code=302)

    session = await db.checkout_sessions.find_one({"session_id": session_id})
    if not session:
        return RedirectResponse(url="/pricing?status=not_found", status_code=302)

    # Apply activation
    await apply_subscription_activation(
        db=db,
        plan_id=session["plan_id"],
        billing_cycle=session.get("billing_cycle", "monthly"),
        user_id=session.get("user_id"),
        tenant_id=session.get("tenant_id"),
        stripe_customer_id=f"cus_sandbox_{uuid.uuid4().hex[:8]}",
        stripe_sub_id=f"sub_sandbox_{uuid.uuid4().hex[:8]}",
        payment_method="Stripe Card (Simulated)"
    )

    # Mark session as completed
    await db.checkout_sessions.update_one({"session_id": session_id}, {"$set": {"status": "completed"}})
    return RedirectResponse(url=f"/app/subscription/success?plan_id={session['plan_id']}", status_code=302)


# Public Plans Endpoint for Dynamic Frontend Consumption
@stripe_router.get("/plans")
async def get_public_subscription_plans():
    """Returns dynamic, Super Admin-managed pricing plans for frontends."""
    db = await ensure_database()
    plans = await db.subscription_plans.find({"is_active": {"$ne": False}}, {"_id": 0}).to_list(100) if db is not None else []
    normalized = [normalize_plan(p) for p in plans]
    return {
        "status": "success",
        "individual": [p for p in normalized if p["audience"] == "individual"],
        "company": [p for p in normalized if p["audience"] == "company"]
    }
