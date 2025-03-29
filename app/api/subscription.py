from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Optional
from ..subscription_manager import SubscriptionManager
from ..auth import get_current_user
from pydantic import BaseModel
import stripe
from fastapi.responses import JSONResponse
import os
from datetime import datetime

router = APIRouter(prefix="/subscription", tags=["subscription"])
subscription_manager = SubscriptionManager()

class SubscriptionCreate(BaseModel):
    payment_method_id: str

class ReferralCode(BaseModel):
    referral_code: str

@router.post("/create")
async def create_subscription(
    subscription: SubscriptionCreate,
    current_user: Dict = Depends(get_current_user)
):
    """Create a new subscription for the current user."""
    try:
        result = subscription_manager.create_subscription(
            current_user["user_id"],
            subscription.payment_method_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def get_subscription_status(
    current_user: Dict = Depends(get_current_user)
):
    """Get current user's subscription status."""
    try:
        return subscription_manager.check_subscription_status(current_user["user_id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/referral-code")
async def get_referral_code(
    current_user: Dict = Depends(get_current_user)
):
    """Get current user's referral code."""
    user = subscription_manager.users.get(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"referral_code": user["referral_code"]}

@router.post("/apply-referral")
async def apply_referral(
    referral: ReferralCode,
    current_user: Dict = Depends(get_current_user)
):
    """Apply a referral code to the current user."""
    try:
        # Find referrer by code
        referrer_id = None
        for user_id, user_data in subscription_manager.users.items():
            if user_data["referral_code"] == referral.referral_code:
                referrer_id = user_id
                break
        
        if not referrer_id:
            raise HTTPException(status_code=404, detail="Invalid referral code")
        
        # Update current user with referral
        current_user_data = subscription_manager.users[current_user["user_id"]]
        current_user_data["referred_by"] = referral.referral_code
        
        # Process referral
        result = subscription_manager.process_referral(referrer_id, current_user["user_id"])
        
        subscription_manager._save_users()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Handle the event
        if event.type == "customer.subscription.updated":
            subscription = event.data.object
            # Update user subscription status
            for user_id, user_data in subscription_manager.users.items():
                if user_data.get("stripe_subscription_id") == subscription.id:
                    user_data["subscription_status"] = "premium" if subscription.status == "active" else "free"
                    user_data["subscription_end"] = datetime.fromtimestamp(subscription.current_period_end).isoformat()
                    subscription_manager._save_users()
                    break
        
        elif event.type == "customer.subscription.deleted":
            subscription = event.data.object
            # Update user subscription status
            for user_id, user_data in subscription_manager.users.items():
                if user_data.get("stripe_subscription_id") == subscription.id:
                    user_data["subscription_status"] = "free"
                    user_data["subscription_end"] = None
                    subscription_manager._save_users()
                    break
        
        return JSONResponse({"status": "success"})
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 