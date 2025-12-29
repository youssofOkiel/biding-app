"""Service for managing bids in Redis"""
import redis
import json
from typing import List, Dict, Optional


class BidService:
    """Service for managing bids in Redis"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.highest_bid_key = "highest_bid"
        self.bid_history_key = "bid_history"
        self.bid_counter_key = "bids:counter"
    
    def get_highest_bid(self) -> Optional[Dict]:
        """Get current highest bid from Redis"""
        bid_data = self.redis.get(self.highest_bid_key)
        return json.loads(bid_data) if bid_data else None
    
    def get_bid_history(self, limit: int = 50) -> List[Dict]:
        """Get bid history from Redis"""
        history = self.redis.lrange(self.bid_history_key, 0, limit - 1)
        return [json.loads(bid) for bid in history]
    
    def save_bid(self, bid_data: Dict) -> None:
        """Save bid to Redis (highest bid and history)"""
        pipe = self.redis.pipeline()
        pipe.set(self.highest_bid_key, json.dumps(bid_data))
        pipe.lpush(self.bid_history_key, json.dumps(bid_data))
        pipe.ltrim(self.bid_history_key, 0, 49)  # Keep last 50 bids
        pipe.execute()
    
    def generate_bid_id(self) -> str:
        """Generate unique bid ID"""
        return str(self.redis.incr(self.bid_counter_key))
    
    def add_to_stream(self, stream_name: str, bid_data: Dict) -> None:
        """Add bid to Redis Stream for cross-pod propagation"""
        self.redis.xadd(stream_name, {
            "bid_id": bid_data["bid_id"],
            "bidder": bid_data["bidder"],
            "amount": str(bid_data["amount"]),
            "timestamp": bid_data["timestamp"]
        })

