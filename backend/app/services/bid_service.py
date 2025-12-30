import redis
import json
from typing import List, Dict, Optional
from .config import HIGHEST_BID_KEY, BID_HISTORY_KEY, BID_COUNTER_KEY

class BidService:
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.highest_bid_key = HIGHEST_BID_KEY
        self.bid_history_key = BID_HISTORY_KEY
        self.bid_counter_key = BID_COUNTER_KEY
    
    def get_highest_bid(self) -> Optional[Dict]:
        bid_data = self.redis.get(self.highest_bid_key)
        return json.loads(bid_data) if bid_data else None
    
    def get_bid_history(self, limit: int = 50) -> List[Dict]:
        history = self.redis.lrange(self.bid_history_key, 0, limit - 1)
        return [json.loads(bid) for bid in history]
    
    def save_bid(self, bid_data: Dict) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self.highest_bid_key, json.dumps(bid_data))
        pipe.lpush(self.bid_history_key, json.dumps(bid_data))
        pipe.ltrim(self.bid_history_key, 0, 49)
        pipe.execute()
    
    def save_bid_atomic(self, bid_data: Dict, max_retries: int = 3) -> bool:
        """
        Atomically save bid only if it's higher than current highest bid.
        Uses Redis WATCH/MULTI/EXEC for optimistic locking to prevent race conditions.
        
        Args:
            bid_data: Dictionary containing bid information (must include 'amount')
            max_retries: Maximum number of retry attempts if WatchError occurs
            
        Returns:
            True if bid was successfully saved, False if bid is too low or max retries exceeded
        """
        bid_amount = float(bid_data.get("amount", 0))
        bid_json = json.dumps(bid_data)
        
        for attempt in range(max_retries):
            try:
                # Watch the highest_bid key for changes
                pipe = self.redis.pipeline()
                pipe.watch(self.highest_bid_key)
                
                # Get current highest bid
                current_data = pipe.get(self.highest_bid_key)
                current_amount = 0.0
                if current_data:
                    current_bid = json.loads(current_data)
                    current_amount = float(current_bid.get("amount", 0))
                
                # Validate that new bid is higher than current
                if bid_amount <= current_amount:
                    pipe.unwatch()
                    return False  # Bid too low
                
                # Start transaction
                pipe.multi()
                pipe.set(self.highest_bid_key, bid_json)
                pipe.lpush(self.bid_history_key, bid_json)
                pipe.ltrim(self.bid_history_key, 0, 49)  # Keep last 50 bids
                
                # Execute transaction (will raise WatchError if key was modified)
                pipe.execute()
                return True  # Successfully saved
                
            except redis.WatchError:
                # Another process modified the highest_bid key, retry
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    # Max retries exceeded
                    return False
            except Exception as e:
                # Unexpected error, log and return False
                print(f"Error in save_bid_atomic: {e}", flush=True)
                return False
        
        return False
    
    def generate_bid_id(self) -> str:
        return str(self.redis.incr(self.bid_counter_key))
    
    def add_to_stream(self, stream_name: str, bid_data: Dict) -> None:
        self.redis.xadd(stream_name, {
            "bid_id": bid_data["bid_id"],
            "bidder": bid_data["bidder"],
            "amount": str(bid_data["amount"]),
            "timestamp": bid_data["timestamp"]
        })

