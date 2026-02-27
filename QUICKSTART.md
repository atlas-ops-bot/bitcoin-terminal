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

### Quick Start (Recommended)

Just run:

```bash
python -m bitcoin_terminal
```

**First Launch:**
- 🔍 Automatically scans your system for Bitcoin directories
- 💾 Saves the found directory to `.env`
- 🚀 Launches the TUI dashboard

**Subsequent Launches:**
- ✅ Reads directory from `.env`
- ⚡ Launches instantly (no scanning needed)
- 🎯 Goes straight to the dashboard

### Manual Scan (Optional)

If you want to scan for directories without launching the TUI:

```bash
python -m bitcoin_terminal scan
```

This will:
- 🔍 Search your system for Bitcoin data directories
- 📊 Display a beautiful table with found directories
- 💾 Show size and status of each directory
- ⚡ Save the first found directory to `.env`

### Force Re-scan

If you moved your Bitcoin directory or want to use a different one:

```bash
python -m bitcoin_terminal --force-scan
```

### TUI Dashboard Features

When running, the dashboard displays:
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

Configuration is stored in `.env` file in the project root.

### Automatic Configuration

On first run, Bitcoin Terminal automatically:
1. Scans for Bitcoin data directory
2. Creates `.env` file
3. Saves the directory path

### Manual Configuration

You can also create/edit `.env` manually (use `.env.example` as template):

```bash
# Copy example file
cp .env.example .env

# Edit with your settings
nano .env
```

### Example .env

```ini
# Bitcoin Data Directory (auto-detected)
BITCOIN_DATADIR=/Users/yourusername/Library/Application Support/Bitcoin

# Bitcoin RPC Configuration (optional - reads from bitcoin.conf)
BITCOIN_RPC_HOST=127.0.0.1
BITCOIN_RPC_PORT=8332
BITCOIN_RPC_USER=your_rpc_username
BITCOIN_RPC_PASSWORD=your_rpc_password

# Display Settings
REFRESH_INTERVAL=5
THEME=dark
```

**Note:** `.env` is in `.gitignore` for security - never commit it to version control!

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
