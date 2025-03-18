import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_TTL

class TransactionCache:
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            socket_timeout=5,
            retry_on_timeout=True,
            decode_responses=True
        )
        self.ttl = REDIS_TTL
        
    async def is_processed(self, tx_hash: str) -> bool:
        try:
            return bool(self.redis.exists(f"tx:{tx_hash}"))
        except redis.ConnectionError:
            print("⚠️ Redis connection failed, skipping cache check")
            return False
        
    async def mark_processed(self, tx_hash: str):
        try:
            self.redis.set(f"tx:{tx_hash}", "1", ex=self.ttl)
        except redis.ConnectionError:
            print("⚠️ Redis connection failed, skipping cache update")