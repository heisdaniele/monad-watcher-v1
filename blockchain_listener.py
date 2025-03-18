import asyncio
from web3 import Web3
from web3.exceptions import ProviderConnectionError
from supabase import create_client
from config import NODE_URL, TRANSFER_THRESHOLD, SUPABASE_URL, SUPABASE_SERVICE_KEY
from redis_helper import TransactionCache

# Initialize clients
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
tx_cache = TransactionCache()

# Create Web3 instance with optimized settings
w3 = Web3(Web3.LegacyWebSocketProvider(
    NODE_URL,
    websocket_kwargs={
        'max_size': 100_000_000,  # Reduced to 100MB
        'ping_interval': 30,
        'ping_timeout': 20,
        'close_timeout': 20
    }
))

# Set to track processed transactions to avoid duplicates.
processed_tx_hashes = set()

# Define token conversion: 1 MON = 10^18 units.
MON_DECIMALS = 10 ** 18

async def send_to_supabase(tx_data):
    """
    Sends a transaction record to Supabase's 'transfers' table using upsert.
    If the transaction already exists (same tx_hash), it will be skipped.
    """
    try:
        formatted_data = {
            "tx_hash": tx_data["tx_hash"],
            "from_addr": tx_data["from_addr"],
            "to_addr": tx_data["to_addr"],
            "amount": float(tx_data["amount"]),
            "block_number": tx_data["blockNumber"]
        }
        # Upsert data into Supabase (insert if not exists)
        response = (supabase.table('transfers')
                   .upsert(formatted_data, 
                          on_conflict='tx_hash',  # Primary key
                          ignore_duplicates=True)
                   .execute())
        
        print(f"✅ Transaction processed: {tx_data['tx_hash'][:10]}... ({tx_data['amount']} MON)")
    except Exception as e:
        print(f"❌ Failed to process transaction: {e}")
        print(f"Response details: {getattr(e, 'response', 'No response details')}")

async def process_block(block_number):
    """Process a single block by getting individual transactions"""
    try:
        # Get only block header first
        block = w3.eth.get_block(block_number, full_transactions=False)
        print(f"📦 Processing block: {block_number}")
        
        # Process transactions one by one
        for tx_hash in block.transactions:
            try:
                # Get individual transaction
                tx = w3.eth.get_transaction(tx_hash)
                if tx and tx.value and tx.value >= TRANSFER_THRESHOLD:
                    await process_transaction(tx, block_number)
            except Exception as e:
                print(f"⚠️ Transaction error ({tx_hash.hex()[:10]}...): {str(e)}")
                continue
                
    except Exception as e:
        print(f"⚠️ Block processing error: {str(e)}")

async def listen_to_blocks():
    print("🚀 Starting blockchain listener...")
    retry_delay = 5
    
    while True:
        try:
            if not w3.is_connected():
                print("⚠️ Reconnecting to Monad node...")
                await asyncio.sleep(retry_delay)
                continue

            current_block = w3.eth.block_number
            while True:
                try:
                    latest_block = w3.eth.block_number
                    if latest_block > current_block:
                        for block_number in range(current_block + 1, latest_block + 1):
                            await process_block(block_number)
                        current_block = latest_block
                    await asyncio.sleep(1)
                
                except (TimeoutError, ProviderConnectionError) as e:
                    print(f"⚠️ Connection error: {str(e)}")
                    await asyncio.sleep(retry_delay)
                    break
                    
        except Exception as e:
            print(f"❌ Critical error: {str(e)}")
            await asyncio.sleep(retry_delay)

async def process_transaction(tx, block_number):
    tx_hash = tx.hash.hex()
    
    # Check Redis cache
    if await tx_cache.is_processed(tx_hash):
        return
        
    human_amount = tx.value / MON_DECIMALS
    tx_data = {
        "tx_hash": tx_hash,
        "from_addr": tx["from"],
        "to_addr": tx.to,
        "amount": f"{human_amount:.2f}",
        "blockNumber": block_number,
    }
    
    print(f"💰 Large transfer detected: {human_amount:.2f} MON")
    await send_to_supabase(tx_data)
    await tx_cache.mark_processed(tx_hash)

if __name__ == "__main__":
    asyncio.run(listen_to_blocks())