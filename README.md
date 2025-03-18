# Monad Blockchain Transaction Watcher

Monitors the Monad blockchain for large transactions and forwards them to a web service.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file with your configuration:
```
NODE_URL=wss://testnet-rpc.monad.xyz
TRANSFER_THRESHOLD=50000000000000000000
WEBSITE_ENDPOINT=your_endpoint_here
```

## Running

```bash
python blockchain_listener.py
```

## Docker Deployment

Build and run with Docker:

```bash
# Build the image
docker build -t monad-watcher .

# Run the container
docker run -d \
  --name monad-watcher \
  --env-file .env \
  monad-watcher
```

Or using docker-compose:

```bash
docker-compose up -d
```