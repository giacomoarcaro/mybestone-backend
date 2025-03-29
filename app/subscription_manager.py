import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
from pathlib import Path
import stripe
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SubscriptionManager:
    def __init__(self):
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
        self.stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.subscription_price_id = os.getenv('STRIPE_PRICE_ID')
        
        # Initialize Stripe
        stripe.api_key = self.stripe_secret_key
        
        # Load user data
        self.users_file = Path("data/users.json")
        self.users_file.parent.mkdir(exist_ok=True)
        self.users = self._load_users()
    
    def _load_users(self) -> Dict:
        """Load user data from file."""
        if self.users_file.exists():
            with open(self.users_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_users(self):
        """Save user data to file."""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def create_user(self, user_id: str, email: str, referral_code: Optional[str] = None) -> Dict:
        """Create a new user with free tier access."""
        user_data = {
            'user_id': user_id,
            'email': email,
            'subscription_status': 'free',
            'subscription_end': None,
            'search_count': 0,
            'referral_code': self._generate_referral_code(user_id),
            'referred_by': referral_code,
            'referrals': [],
            'created_at': datetime.now().isoformat()
        }
        
        self.users[user_id] = user_data
        self._save_users()
        return user_data
    
    def _generate_referral_code(self, user_id: str) -> str:
        """Generate a unique referral code for a user."""
        import hashlib
        return hashlib.md5(user_id.encode()).hexdigest()[:8].upper()
    
    def create_subscription(self, user_id: str, payment_method_id: str) -> Dict:
        """Create a premium subscription for a user."""
        try:
            # Create or get Stripe customer
            user = self.users.get(user_id)
            if not user:
                raise ValueError("User not found")
            
            if 'stripe_customer_id' not in user:
                customer = stripe.Customer.create(
                    email=user['email'],
                    payment_method=payment_method_id
                )
                user['stripe_customer_id'] = customer.id
                self._save_users()
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=user['stripe_customer_id'],
                items=[{'price': self.subscription_price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent']
            )
            
            # Update user data
            user['subscription_status'] = 'premium'
            user['subscription_end'] = (datetime.now() + timedelta(days=30)).isoformat()
            user['stripe_subscription_id'] = subscription.id
            self._save_users()
            
            return {
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            }
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            raise
    
    def process_referral(self, referrer_id: str, new_user_id: str) -> Dict:
        """Process a successful referral."""
        try:
            referrer = self.users.get(referrer_id)
            new_user = self.users.get(new_user_id)
            
            if not referrer or not new_user:
                raise ValueError("User not found")
            
            # Add referral to referrer's list
            if new_user_id not in referrer['referrals']:
                referrer['referrals'].append(new_user_id)
                
                # Give referrer 1 month of premium access
                referrer['subscription_status'] = 'premium'
                referrer['subscription_end'] = (datetime.now() + timedelta(days=30)).isoformat()
                
                self._save_users()
                
                return {
                    'success': True,
                    'message': 'Referral processed successfully'
                }
            
            return {
                'success': False,
                'message': 'Referral already processed'
            }
            
        except Exception as e:
            logger.error(f"Error processing referral: {str(e)}")
            raise
    
    def check_subscription_status(self, user_id: str) -> Dict:
        """Check user's subscription status and search limits."""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        is_premium = user['subscription_status'] == 'premium'
        can_search = True
        
        if not is_premium:
            # Free tier limits: 10 searches per day
            today = datetime.now().date()
            if 'last_search_date' in user:
                last_search = datetime.fromisoformat(user['last_search_date']).date()
                if today > last_search:
                    user['search_count'] = 0
                    user['last_search_date'] = today.isoformat()
                    self._save_users()
            
            can_search = user['search_count'] < 10
        
        return {
            'is_premium': is_premium,
            'can_search': can_search,
            'search_count': user['search_count'],
            'subscription_end': user['subscription_end']
        }
    
    def increment_search_count(self, user_id: str):
        """Increment user's search count."""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        user['search_count'] += 1
        user['last_search_date'] = datetime.now().isoformat()
        self._save_users()

def main():
    # Example usage
    manager = SubscriptionManager()
    
    # Create a new user
    user = manager.create_user("user123", "test@example.com")
    print(f"Created user: {user}")
    
    # Create another user with referral
    referred_user = manager.create_user("user456", "referred@example.com", user['referral_code'])
    print(f"Created referred user: {referred_user}")
    
    # Process referral
    result = manager.process_referral(user['user_id'], referred_user['user_id'])
    print(f"Referral result: {result}")
    
    # Check subscription status
    status = manager.check_subscription_status(user['user_id'])
    print(f"Subscription status: {status}")

if __name__ == "__main__":
    main() 