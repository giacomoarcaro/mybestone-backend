from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List
from ..subscription_manager import SubscriptionManager
from ..auth import get_current_user, get_admin_user
from datetime import datetime, timedelta
import stripe
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
subscription_manager = SubscriptionManager()

class DashboardStats(BaseModel):
    total_users: int
    premium_users: int
    free_users: int
    total_revenue: float
    monthly_revenue: float
    total_referrals: int
    active_referrals: int

@router.get("/stats")
async def get_dashboard_stats(
    current_user: Dict = Depends(get_admin_user)
):
    """Get overall dashboard statistics."""
    try:
        # Calculate user stats
        total_users = len(subscription_manager.users)
        premium_users = sum(1 for user in subscription_manager.users.values() 
                          if user["subscription_status"] == "premium")
        free_users = total_users - premium_users
        
        # Calculate revenue
        total_revenue = 0
        monthly_revenue = 0
        current_month = datetime.now().month
        
        for user in subscription_manager.users.values():
            if user.get("stripe_customer_id"):
                try:
                    customer = stripe.Customer.retrieve(user["stripe_customer_id"])
                    for subscription in customer.subscriptions.list():
                        if subscription.status == "active":
                            total_revenue += subscription.items.data[0].price.unit_amount / 100
                            if datetime.fromtimestamp(subscription.created).month == current_month:
                                monthly_revenue += subscription.items.data[0].price.unit_amount / 100
                except:
                    continue
        
        # Calculate referral stats
        total_referrals = sum(len(user["referrals"]) for user in subscription_manager.users.values())
        active_referrals = sum(1 for user in subscription_manager.users.values() 
                             if user.get("referred_by") and user["subscription_status"] == "premium")
        
        return DashboardStats(
            total_users=total_users,
            premium_users=premium_users,
            free_users=free_users,
            total_revenue=total_revenue,
            monthly_revenue=monthly_revenue,
            total_referrals=total_referrals,
            active_referrals=active_referrals
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/revenue-history")
async def get_revenue_history(
    months: int = 12,
    current_user: Dict = Depends(get_admin_user)
):
    """Get historical revenue data."""
    try:
        revenue_history = []
        current_date = datetime.now()
        
        for i in range(months):
            month_date = current_date - timedelta(days=30*i)
            month_revenue = 0
            
            for user in subscription_manager.users.values():
                if user.get("stripe_customer_id"):
                    try:
                        customer = stripe.Customer.retrieve(user["stripe_customer_id"])
                        for subscription in customer.subscriptions.list():
                            if (subscription.status == "active" and 
                                datetime.fromtimestamp(subscription.created).month == month_date.month and
                                datetime.fromtimestamp(subscription.created).year == month_date.year):
                                month_revenue += subscription.items.data[0].price.unit_amount / 100
                    except:
                        continue
            
            revenue_history.append({
                "month": month_date.strftime("%Y-%m"),
                "revenue": month_revenue
            })
        
        return revenue_history
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/top-referrers")
async def get_top_referrers(
    limit: int = 10,
    current_user: Dict = Depends(get_admin_user)
):
    """Get top users by number of successful referrals."""
    try:
        referrer_stats = []
        
        for user_id, user_data in subscription_manager.users.items():
            successful_referrals = sum(1 for ref_id in user_data["referrals"] 
                                     if subscription_manager.users.get(ref_id, {}).get("subscription_status") == "premium")
            
            if successful_referrals > 0:
                referrer_stats.append({
                    "user_id": user_id,
                    "email": user_data["email"],
                    "successful_referrals": successful_referrals,
                    "total_referrals": len(user_data["referrals"])
                })
        
        # Sort by successful referrals and limit
        referrer_stats.sort(key=lambda x: x["successful_referrals"], reverse=True)
        return referrer_stats[:limit]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user-growth")
async def get_user_growth(
    days: int = 30,
    current_user: Dict = Depends(get_admin_user)
):
    """Get user growth statistics."""
    try:
        growth_data = []
        current_date = datetime.now()
        
        for i in range(days):
            date = current_date - timedelta(days=i)
            new_users = sum(1 for user in subscription_manager.users.values() 
                          if datetime.fromisoformat(user["created_at"]).date() == date.date())
            
            growth_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "new_users": new_users,
                "total_users": sum(1 for user in subscription_manager.users.values() 
                                 if datetime.fromisoformat(user["created_at"]).date() <= date.date())
            })
        
        return growth_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 