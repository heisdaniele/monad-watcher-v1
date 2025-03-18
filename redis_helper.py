import redis
import time
from config import REDIS_HOST, REDIS_PORT, REDIS_TTL

class TransactionCache:
    def __init__(self):
        self.redis = None
        self.ttl = REDIS_TTL
        self.connect_with_retry()

    def connect_with_retry(self, max_retries=5):
        """Attempt to connect to Redis with retries"""
        retry_count = 0
        while not self.redis and retry_count < max_retries:
            try:
                self.redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    decode_responses=True,
                    health_check_interval=30
                )
                # Test connection
                self.redis.ping()
                print("✅ Connected to Redis successfully")
            except redis.ConnectionError:
                retry_count += 1
                print(f"⚠️ Redis connection attempt {retry_count}/{max_retries} failed")
                time.sleep(2)
                self.redis = None

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