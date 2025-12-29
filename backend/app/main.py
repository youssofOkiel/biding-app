"""FastAPI application main file"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional

from services.bid_service import BidService
from services.connection_manager import ConnectionManager
from services.stream_processor import StreamProcessor
from services.config import REDIS_HOST, REDIS_PORT, STREAM_NAME


# Initialize Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

# Initialize services
bid_service = BidService(redis_client)
connection_manager = ConnectionManager()
stream_processor = StreamProcessor(redis_client, connection_manager, STREAM_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    background_task = None
    
    try:
        print("STARTUP: Initializing application...", flush=True)
        redis_client.ping()
        print("✓ Redis connection successful", flush=True)
        background_task = asyncio.create_task(stream_processor.process_messages())
        print("✓ Started stream processor", flush=True)
        print("STARTUP: Complete!", flush=True)
    except Exception as e:
        print(f"✗ Startup error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    
    yield
    
    print("Shutting down...", flush=True)
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Bidding Application", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Bidding Application API"}


@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        redis_status = "connected"
    except:
        redis_status = "disconnected"
    
    return {"status": "healthy", "redis": redis_status}


@app.get("/api/bids/highest")
async def get_highest_bid():
    """Get current highest bid"""
    bid = bid_service.get_highest_bid()
    if bid:
        return bid
    return {"amount": 0, "bidder": None, "timestamp": None, "bid_id": None}


@app.get("/api/bids/history")
async def get_bid_history(limit: int = 50):
    """Get bid history"""
    return {"history": bid_service.get_bid_history(limit)}


@app.websocket("/ws/bid")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time bidding"""
    await connection_manager.connect(websocket)
    
    try:
        # Send initial state
        highest_bid = bid_service.get_highest_bid()
        history = bid_service.get_bid_history(50)
        
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "data": {
                "highest_bid": highest_bid or {"amount": 0, "bidder": None, "timestamp": None, "bid_id": None},
                "history": history
            }
        }))
        
        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "submit_bid":
                error = await _validate_and_process_bid(message, websocket)
                if error:
                    await connection_manager.send_message(json.dumps({
                        "type": "error",
                        "message": error
                    }), websocket)
    
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


async def _validate_and_process_bid(message: Dict, websocket: WebSocket) -> Optional[str]:
    """Validate and process a bid submission"""
    bidder = message.get("bidder", "").strip()
    
    try:
        amount = float(message.get("amount", 0))
    except (ValueError, TypeError):
        return "Invalid bid amount"
    
    # Validation
    if not bidder:
        return "Bidder name is required"
    
    if amount <= 0:
        return "Bid amount must be greater than 0"
    
    current_highest = bid_service.get_highest_bid()
    current_amount = current_highest.get("amount", 0) if current_highest else 0
    
    if amount <= current_amount:
        return f"Bid must be higher than current highest bid (${current_amount:.2f})"
    
    # Create bid
    bid_data = {
        "bid_id": bid_service.generate_bid_id(),
        "bidder": bidder,
        "amount": amount,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Save to Redis
    bid_service.save_bid(bid_data)
    bid_service.add_to_stream(STREAM_NAME, bid_data)
    
    # Send confirmation
    await connection_manager.send_message(json.dumps({
        "type": "bid_accepted",
        "data": bid_data
    }), websocket)
    
    return None
