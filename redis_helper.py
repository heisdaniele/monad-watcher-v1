import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_TTL

class TransactionCache:
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
        self.ttl = REDIS_TTL
        
    async def is_processed(self, tx_hash: str) -> bool:
        """Check if transaction has been processed"""
        return bool(self.redis.exists(f"tx:{tx_hash}"))
        
    async def mark_processed(self, tx_hash: str):
        """Mark transaction as processed"""
        self.redis.set(f"tx:{tx_hash}", "1", ex=self.ttl)