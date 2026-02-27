# Bitcoin Terminal 🟠

A beautiful, modern TUI (Terminal User Interface) for monitoring your Bitcoin Node.

## Features

- 🔍 **Auto-Discovery**: Automatically searches for Bitcoin data directories on your system
- 📊 **Real-time Monitoring**: Track your node's performance and status
- 🎨 **Beautiful Interface**: Modern terminal UI with colors, progress bars, and animations
- ⚡ **Fast & Lightweight**: Built with Python and optimized for performance

## Screenshots

_Coming soon..._

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/bitcoin-terminal.git
cd bitcoin-terminal

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m bitcoin_terminal
```

## Usage

```bash
# Start the TUI (smart launcher - scans only if needed)
python -m bitcoin_terminal

# First run: Automatically scans for Bitcoin directory, saves to .env, then launches
# Subsequent runs: Uses saved directory from .env, launches immediately

# Force re-scan for Bitcoin directories
python -m bitcoin_terminal scan
# or
python -m bitcoin_terminal --force-scan

# Connect to specific data directory (overrides .env)
python -m bitcoin_terminal --datadir /path/to/bitcoin
```

### Smart Directory Detection

Bitcoin Terminal intelligently manages your Bitcoin data directory:

1. **First Launch**: Automatically scans your system, finds Bitcoin directory, saves to `.env`
2. **Subsequent Launches**: Uses saved directory, skips scanning for instant startup
3. **Validation**: Checks if directory still exists before launching
4. **Override**: Use `--datadir` or `--force-scan` to change directory

## Requirements

- Python 3.8+
- Bitcoin Core node (optional, for full functionality)

## Configuration

Configuration is stored in `config.ini`. On first run, the app will auto-detect your Bitcoin data directory.

## Development

This project is in **ALPHA** stage. Contributions welcome!

## License

MIT License - See LICENSE file for details

## Acknowledgments

Inspired by the excellent [warden_terminal](https://github.com/pxsocs/warden_terminal) project.
