import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Blockchain settings
NODE_URL = os.getenv('NODE_URL', "wss://testnet-rpc.monad.xyz")
TRANSFER_THRESHOLD = int(os.getenv('TRANSFER_THRESHOLD', 50 * (10 ** 18)))

# Supabase settings
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Redis settings
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_TTL = int(os.getenv('REDIS_TTL', 86400))  # 24 hours in seconds

# Validate configurations
if not SUPABASE_SERVICE_KEY or not SUPABASE_SERVICE_KEY.startswith('eyJ'):
    raise ValueError("Invalid or missing Supabase service role key")