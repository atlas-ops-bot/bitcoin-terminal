# Quick Start Guide 🚀

## Installation

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. You're ready!
```

## Usage

### 1. Scan for Bitcoin Directories

Find your Bitcoin Core data directory automatically:

```bash
python -m bitcoin_terminal scan
```

This will:
- 🔍 Search your system for Bitcoin data directories
- 📊 Display a beautiful table with found directories
- 💾 Show size and status of each directory
- ⚡ Save the first found directory to config

### 2. Run the TUI Dashboard

Launch the full terminal interface:

```bash
python -m bitcoin_terminal
```

Or simply:

```bash
python -m bitcoin_terminal run
```

This will display:
- ⚡ **Node Status**: Connection status, block height, sync progress, peer count
- ⛓️  **Blockchain Info**: Network, difficulty, size on disk
- 💾 **Mempool**: Transaction count and size
- 🔄 Auto-refresh every 5 seconds

### 3. Keyboard Shortcuts

When running the TUI:
- `R` - Manual refresh
- `S` - Scan for Bitcoin directories
- `Q` - Quit

## Configuration

Configuration is automatically created at:
- **macOS/Linux**: `~/.config/bitcoin-terminal/config.ini`
- **Windows**: `%APPDATA%\bitcoin-terminal\config.ini`

### Example config.ini

```ini
[bitcoin]
datadir = /Users/yourusername/Library/Application Support/Bitcoin
rpc_host = 127.0.0.1
rpc_port = 8332
rpc_user = your_rpc_username
rpc_password = your_rpc_password

[display]
theme = dark
refresh_interval = 5
show_mempool = true
show_peers = true
```

## Connecting to Bitcoin Core

For full functionality, you need Bitcoin Core running with RPC enabled.

### Enable RPC in bitcoin.conf

Add to your `bitcoin.conf` (usually in your Bitcoin data directory):

```ini
# RPC Server
server=1
rpcuser=your_username
rpcpassword=your_secure_password
rpcport=8332

# Optional: restrict RPC to localhost
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
```

### Test Connection

The TUI will automatically connect if it finds your bitcoin.conf. You'll see:

- ✅ **Green "ONLINE"** - Connected successfully
- 🟡 **Yellow "OFFLINE"** - Cannot connect (check if Bitcoin Core is running)
- 🔴 **Red "ERROR"** - Connection error (check RPC credentials)

## Troubleshooting

### Scanner finds no directories

- Make sure Bitcoin Core has been run at least once
- Check if Bitcoin Core is installed in a custom location
- Use `--datadir` flag: `python -m bitcoin_terminal --datadir /path/to/bitcoin`

### Cannot connect to node

1. Check Bitcoin Core is running: `bitcoin-cli getblockcount`
2. Verify RPC is enabled in bitcoin.conf
3. Check RPC credentials match your config
4. Ensure Bitcoin Core is fully started (check debug.log)

### Permission errors during scan

This is normal - the scanner skips directories it can't access.

## Next Steps

- ⭐ Star the repo on GitHub
- 🐛 Report issues
- 🤝 Contribute features
- 📖 Read the full documentation

## Development

```bash
# Install in development mode
pip install -e .

# Run from anywhere
bitcoin-terminal scan
```

Enjoy monitoring your Bitcoin Node! ⚡🟠
