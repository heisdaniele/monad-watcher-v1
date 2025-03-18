import redis
import time
from config import REDIS_HOST, REDIS_PORT, REDIS_TTL

class TransactionCache:
    def __init__(self):
        self.redis = None
        self.ttl = REDIS_TTL
        self.max_retries = 5
        self.initial_retry_delay = 1
        self.connect_with_retry()

    def connect_with_retry(self):
        """Attempt to connect to Redis with exponential backoff"""
        retry_count = 0
        retry_delay = self.initial_retry_delay

        while not self.redis and retry_count < self.max_retries:
            try:
                print(f"🔄 Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
                self.redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    decode_responses=True,
                    health_check_interval=30
                )
                # Test connection
                self.redis.ping()
                print("✅ Connected to Redis successfully")
                return True
            except redis.ConnectionError as e:
                retry_count += 1
                print(f"⚠️ Redis connection attempt {retry_count}/{self.max_retries} failed: {str(e)}")
                if retry_count < self.max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                self.redis = None
        return False

    async def is_processed(self, tx_hash: str) -> bool:
        """Check if transaction has been processed"""
        try:
            if not self.redis:
                self.connect_with_retry()
            return bool(self.redis and self.redis.exists(f"tx:{tx_hash}"))
        except redis.ConnectionError:
            print("⚠️ Redis connection failed, skipping cache check")
            return False

    async def mark_processed(self, tx_hash: str):
        """Mark transaction as processed"""
        try:
            if not self.redis:
                self.connect_with_retry()
            if self.redis:
                self.redis.set(f"tx:{tx_hash}", "1", ex=self.ttl)
        except redis.ConnectionError:
            print("⚠️ Redis connection failed, skipping cache update")