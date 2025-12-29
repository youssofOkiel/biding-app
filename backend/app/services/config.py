"""Configuration constants"""
import os

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Stream configuration
STREAM_NAME = "bids_stream"

