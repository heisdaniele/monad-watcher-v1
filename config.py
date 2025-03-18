import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

NODE_URL = os.getenv('NODE_URL', "wss://testnet-rpc.monad.xyz")
TRANSFER_THRESHOLD = int(os.getenv('TRANSFER_THRESHOLD', 50 * (10 ** 18)))
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Using service role key

# Validate Supabase configuration
if not SUPABASE_SERVICE_KEY or not SUPABASE_SERVICE_KEY.startswith('eyJ'):
    raise ValueError("Invalid or missing Supabase service role key")
