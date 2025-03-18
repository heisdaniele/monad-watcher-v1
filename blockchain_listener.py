import asyncio
from web3 import Web3
from web3.exceptions import ProviderConnectionError
from supabase import create_client
from config import NODE_URL, TRANSFER_THRESHOLD, SUPABASE_URL, SUPABASE_SERVICE_KEY
from redis_helper import TransactionCache

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Create Web3 instance with optimized settings
w3 = Web3(Web3.LegacyWebSocketProvider(
    NODE_URL,
    websocket_kwargs={
        'max_size': 1_000_000_000,  # 1GB max message size
        'ping_interval': 30,
        'ping_timeout': 10,
        'close_timeout': 10
    }
))

# Set to track processed transactions to avoid duplicates.
processed_tx_hashes = set()

# Define token conversion: 1 MON = 10^18 units.
MON_DECIMALS = 10 ** 18

# Initialize cache
tx_cache = TransactionCache()

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

async def listen_to_blocks():
    print("🚀 Starting blockchain listener...")
    while True:
        try:
            if not w3.is_connected():
                print("⚠️ Reconnecting to Monad node...")
                await asyncio.sleep(5)
                continue

            current_block = w3.eth.block_number
            while True:
                try:
                    latest_block = w3.eth.block_number
                    if latest_block > current_block:
                        for block_number in range(current_block + 1, latest_block + 1):
                            try:
                                print(f"📦 Processing block: {block_number}")
                                block = w3.eth.get_block(block_number, full_transactions=False)
                                
                                # Get transactions in chunks
                                for tx_hash in block.transactions:
                                    try:
                                        tx = w3.eth.get_transaction(tx_hash)
                                        if tx and tx.value and tx.value >= TRANSFER_THRESHOLD:
                                            await process_transaction(tx, block_number)
                                    except Exception as e:
                                        print(f"⚠️ Error processing transaction {tx_hash}: {e}")
                                        continue
                                
                            except Exception as e:
                                print(f"⚠️ Error processing block {block_number}: {e}")
                                continue
                        
                        current_block = latest_block
                    await asyncio.sleep(5)
                
                except (TimeoutError, ProviderConnectionError) as e:
                    print(f"⚠️ Connection error: {e}")
                    break
                
        except Exception as e:
            print(f"❌ Critical error: {e}")
            await asyncio.sleep(5)

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