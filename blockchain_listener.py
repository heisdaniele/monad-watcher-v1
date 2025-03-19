import asyncio
import logging
import time
from web3 import Web3
from web3.exceptions import ProviderConnectionError
from supabase import create_client
from config import NODE_URL, TRANSFER_THRESHOLD, SUPABASE_URL, SUPABASE_SERVICE_KEY

# Configure logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Add retry configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1

def initialize_web3(max_retries=MAX_RETRIES, retry_delay=INITIAL_RETRY_DELAY):
    """Initialize Web3 with connection verification and retry logic"""
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Attempting to connect to node (attempt {attempt + 1}/{max_retries})")
            
            # Updated WebSocket settings without ssl_verify
            provider = Web3.LegacyWebSocketProvider(
                NODE_URL,
                websocket_kwargs={
                    'max_size': 100_000_000,    # Reduced to 100MB
                    'ping_interval': 15,         # More frequent pings
                    'ping_timeout': 10,          # Shorter timeout
                    'close_timeout': 5,          # Quicker close
                    'extra_headers': {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                    }
                }
            )
            w3 = Web3(provider)
            
            # Enhanced connection verification
            if not w3.is_connected():
                logger.error("❌ Initial connection failed")
                raise ConnectionError("Failed initial connection check")
            
            # Test chain connection with timeout
            try:
                chain_id = w3.eth.chain_id
                block = w3.eth.get_block('latest')
                logger.info(f"✅ Connected to chain {chain_id}, latest block: {block.number}")
                return w3
            except Exception as chain_error:
                logger.error(f"❌ Chain verification failed: {str(chain_error)}")
                raise

        except Exception as e:
            logger.warning(f"⚠️ Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"😴 Waiting {sleep_time} seconds before retry...")
                time.sleep(sleep_time)
            else:
                logger.error("❌ All connection attempts failed")
                return None

# Initialize Web3 with retries
w3 = initialize_web3()
if not w3:
    logger.error("❌ Could not establish connection to QuickNode after multiple attempts")
    raise ConnectionError("Failed to connect to QuickNode after exhausting retries")

# Rate limiting for QuickNode
REQUESTS_PER_SECOND = 10  # Conservative rate limit
REQUEST_COOLDOWN = 1 / REQUESTS_PER_SECOND
MON_DECIMALS = 10 ** 18

async def check_sync_status():
    """Monitor block sync status with enhanced error handling"""
    try:
        if not w3.is_connected():
            logger.error("❌ Not connected to QuickNode")
            return None, None
            
        current = w3.eth.block_number
        await asyncio.sleep(REQUEST_COOLDOWN)
        
        latest = w3.eth.block_number
        await asyncio.sleep(REQUEST_COOLDOWN)
        
        if latest - current > 10:
            logger.warning(f"⚠️ Behind by {latest - current} blocks")
        return current, latest
    except ProviderConnectionError as e:
        logger.error(f"❌ QuickNode connection error: {str(e)}")
        return None, None
    except Exception as e:
        logger.error(f"❌ Sync check failed: {str(e)}")
        return None, None

async def send_to_supabase(tx_data):
    """Send transaction with upsert for deduplication"""
    try:
        formatted_data = {
            "tx_hash": tx_data["tx_hash"],
            "from_addr": tx_data["from_addr"],
            "to_addr": tx_data["to_addr"],
            "amount": float(tx_data["amount"]),
            "block_number": tx_data["blockNumber"]
        }
        response = (supabase.table('transfers')
                   .upsert(formatted_data, 
                          on_conflict='tx_hash',
                          ignore_duplicates=True)
                   .execute())
        logger.info(f"✅ Transaction saved: {tx_data['tx_hash'][:10]}... ({tx_data['amount']} MON)")
    except Exception as e:
        logger.error(f"❌ Supabase error: {e}")

async def process_block(block_number):
    """Process single block with rate limiting"""
    try:
        block = w3.eth.get_block(block_number, full_transactions=True)
        await asyncio.sleep(REQUEST_COOLDOWN)
        
        logger.info(f"📦 Processing block: {block_number}")
        
        for tx in block.transactions:
            if tx.value and tx.value >= TRANSFER_THRESHOLD:
                await process_transaction(tx, block_number)
                await asyncio.sleep(REQUEST_COOLDOWN)
    except Exception as e:
        logger.error(f"❌ Block {block_number} error: {e}")

async def listen_to_blocks():
    """Main loop with sync monitoring"""
    logger.info("🚀 Starting blockchain listener with QuickNode...")
    retry_delay = 5
    
    while True:
        try:
            current_block, latest_block = await check_sync_status()
            if not current_block:
                await asyncio.sleep(retry_delay)
                continue
                
            while True:
                try:
                    for block_number in range(current_block + 1, latest_block + 1):
                        await process_block(block_number)
                    current_block = latest_block
                    
                    # Check sync status periodically
                    await asyncio.sleep(5)
                    current_block, latest_block = await check_sync_status()
                    
                except (TimeoutError, ProviderConnectionError) as e:
                    logger.error(f"⚠️ Connection error: {e}")
                    await asyncio.sleep(retry_delay)
                    break
        except Exception as e:
            logger.error(f"❌ Critical error: {e}")
            await asyncio.sleep(retry_delay)

async def process_transaction(tx, block_number):
    """Process a single transaction"""
    tx_hash = tx.hash.hex()
    human_amount = tx.value / MON_DECIMALS
    
    tx_data = {
        "tx_hash": tx_hash,
        "from_addr": tx["from"],
        "to_addr": tx.to,
        "amount": f"{human_amount:.2f}",
        "blockNumber": block_number,
    }
    
    logger.info(f"💰 Large transfer detected: {human_amount:.2f} MON")
    await send_to_supabase(tx_data)

if __name__ == "__main__":
    asyncio.run(listen_to_blocks())