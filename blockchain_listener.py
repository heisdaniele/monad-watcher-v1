import asyncio
from web3 import Web3
from web3.exceptions import ProviderConnectionError
from supabase import create_client
from config import NODE_URL, TRANSFER_THRESHOLD, SUPABASE_URL, SUPABASE_SERVICE_KEY

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Create Web3 instance with optimized settings
w3 = Web3(Web3.LegacyWebSocketProvider(
    NODE_URL,
    websocket_kwargs={
        'max_size': 100_000_000,  # 100MB
        'ping_interval': 30,
        'ping_timeout': 20,
        'close_timeout': 20
    }
))

# Rate limiting settings
REQUESTS_PER_SECOND = 20  # Keep below 25/s limit
REQUEST_COOLDOWN = 1 / REQUESTS_PER_SECOND

# Define token conversion
MON_DECIMALS = 10 ** 18

async def send_to_supabase(tx_data):
    """Send transaction to Supabase with upsert for deduplication"""
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
        print(f"✅ Transaction processed: {tx_data['tx_hash'][:10]}... ({tx_data['amount']} MON)")
    except Exception as e:
        print(f"❌ Failed to process transaction: {e}")

async def process_block(block_number):
    """Process a single block with rate limiting"""
    try:
        print(f"📦 Processing block: {block_number}")
        
        # Get block with just transaction hashes first
        block = w3.eth.get_block(block_number, full_transactions=False)
        await asyncio.sleep(REQUEST_COOLDOWN)  # Rate limiting
        
        # Process transactions one by one with rate limiting
        for tx_hash in block.transactions:
            try:
                await asyncio.sleep(REQUEST_COOLDOWN)  # Rate limiting
                tx = w3.eth.get_transaction(tx_hash)
                if tx and tx.value and tx.value >= TRANSFER_THRESHOLD:
                    await process_transaction(tx, block_number)
            except Exception as e:
                if "request limit reached" in str(e):
                    print(f"🔄 Rate limit hit, cooling down...")
                    await asyncio.sleep(5)  # Longer cooldown on rate limit
                    continue
                print(f"⚠️ Transaction error ({tx_hash.hex()[:10]}...): {str(e)}")
                continue
                
    except Exception as e:
        print(f"⚠️ Block processing error: {str(e)}")
        await asyncio.sleep(1)

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
            await asyncio.sleep(REQUEST_COOLDOWN)  # Rate limiting
            
            while True:
                try:
                    await asyncio.sleep(REQUEST_COOLDOWN)  # Rate limiting
                    latest_block = w3.eth.block_number
                    if latest_block > current_block:
                        for block_number in range(current_block + 1, latest_block + 1):
                            await process_block(block_number)
                            await asyncio.sleep(REQUEST_COOLDOWN)  # Rate limiting
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
    
    print(f"💰 Large transfer detected: {human_amount:.2f} MON")
    await send_to_supabase(tx_data)

if __name__ == "__main__":
    asyncio.run(listen_to_blocks())