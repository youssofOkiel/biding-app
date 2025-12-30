import redis
import asyncio
import json
from typing import Dict
from .connection_manager import ConnectionManager


class StreamProcessor:
    
    def __init__(self, redis_client: redis.Redis, connection_manager: ConnectionManager, stream_name: str):
        self.redis = redis_client
        self.manager = connection_manager
        self.stream_name = stream_name
        self.last_id = "$"
    
    async def process_messages(self):
        print("Stream processor started, waiting for messages...", flush=True)
        
        while True:
            try:
                # Read messages from stream (non-blocking via executor)
                loop = asyncio.get_event_loop()
                messages = await loop.run_in_executor(
                    None,
                    lambda: self.redis.xread({self.stream_name: self.last_id}, count=10, block=1000)
                )
                
                if not messages:
                    continue
                
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        try:
                            bid_data = self._parse_message(fields)
                            await self.manager.broadcast(json.dumps({
                                "type": "new_bid",
                                "data": bid_data
                            }))
                            self.last_id = msg_id
                        except Exception as e:
                            print(f"Error processing message {msg_id}: {e}", flush=True)
            
            except redis.ResponseError as e:
                print(f"Redis error: {e}", flush=True)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Stream processing error: {e}", flush=True)
                await asyncio.sleep(1)
    
    def _parse_message(self, fields) -> Dict:
        if isinstance(fields, list):
            field_dict = {}
            for i in range(0, len(fields), 2):
                if i + 1 < len(fields):
                    field_dict[fields[i]] = fields[i + 1]
            fields = field_dict
        
        return {
            "bid_id": fields.get("bid_id") or "",
            "bidder": fields.get("bidder") or "",
            "amount": float(fields.get("amount", 0)),
            "timestamp": fields.get("timestamp") or ""
        }

