import asyncio
from web3 import Web3
from config import NODE_URL, TRANSFER_THRESHOLD
from telegram_notifier import send_telegram_notification
from website_notifier import send_to_website

# Create a Web3 instance using the LegacyWebSocketProvider.
w3 = Web3(Web3.LegacyWebSocketProvider(NODE_URL))

# Set to track processed transactions to avoid duplicates.
processed_tx_hashes = set()

# Define token conversion: 1 MON = 10^18 units.
MON_DECIMALS = 10 ** 18

async def listen_to_blocks():
    print("Starting blockchain listener...")
    current_block = w3.eth.block_number
    while True:
        try:
            latest_block = w3.eth.block_number
            if latest_block > current_block:
                for block_number in range(current_block + 1, latest_block + 1):
                    print(f"Processing block: {block_number}")
                    block = w3.eth.get_block(block_number, full_transactions=True)
                    await process_block(block)
                current_block = latest_block
            await asyncio.sleep(5)
        except Exception as e:
            print("Error in blockchain listener:", e)
            await asyncio.sleep(5)

async def process_block(block):
    for tx in block.transactions:
        # Process only transactions that exceed the threshold.
        if tx.value and tx.value >= TRANSFER_THRESHOLD:
            tx_hash = tx.hash.hex()
            if tx_hash in processed_tx_hashes:
                continue
            processed_tx_hashes.add(tx_hash)
            human_amount = tx.value / MON_DECIMALS
            tx_data = {
                "tx_hash": tx_hash,
                "from_addr": tx["from"],
                "to_addr": tx.to,
                "amount": f"{human_amount:.2f}",
                "blockNumber": block.number,
            }
            print("Large transfer detected:", tx_data)
            await send_to_website(tx_data)

if __name__ == "__main__":
    asyncio.run(listen_to_blocks())
