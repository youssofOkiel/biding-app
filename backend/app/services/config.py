"""Configuration constants"""
import os

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Stream configuration
STREAM_NAME = "bids_stream"
HIGHEST_BID_KEY = "highest_bid"
BID_HISTORY_KEY = "bid_history"
BID_COUNTER_KEY = "bids:counter"

