# Quick Start

## 1. Install

```bash
git clone https://github.com/CRTao/bitcoin-terminal.git
cd bitcoin-terminal
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 2. Run

```bash
python -m bitcoin_terminal
```

The **setup wizard** runs automatically on first launch:

1. Scans your system for Bitcoin data directories and external drives
2. Probes localhost for RPC ports (8332 / 18332 / 18443 / 38332)
3. Tests the RPC connection (tries cookie auth first, then asks for credentials)
4. Saves everything to `.env`
5. Launches the dashboard

## 3. Requirements

- **Python 3.8+**
- **Bitcoin Core** running with `server=1` in `bitcoin.conf`

If your node is already running with RPC enabled, the wizard handles the rest.

## 4. CLI Options

```bash
python -m bitcoin_terminal                # Launch (wizard on first run)
python -m bitcoin_terminal --setup        # Re-run wizard
python -m bitcoin_terminal --datadir /path/to/bitcoin
python -m bitcoin_terminal --force-scan   # Re-scan directories
python -m bitcoin_terminal scan           # Scan only, no dashboard
```

## 5. Key Controls

| Key | Action |
|-----|--------|
| `c` | Config editor |
| `l` | Log viewer |
| `r` | Matrix Rain |
| `R` | Force refresh |
| `q` | Quit |

## 6. Manual Configuration

If the wizard doesn't work, create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
BITCOIN_DATADIR=/path/to/your/bitcoin/datadir
BITCOIN_RPC_HOST=127.0.0.1
BITCOIN_RPC_PORT=8332
BITCOIN_RPC_USER=your_rpc_user
BITCOIN_RPC_PASSWORD=your_rpc_password
```

Then run `python -m bitcoin_terminal` again.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No Bitcoin directories found" | Make sure Bitcoin Core has run at least once, or use `--datadir` |
| RPC connection failed | Check `server=1` in `bitcoin.conf` and that the node is running |
| Auth errors | Verify `rpcuser` / `rpcpassword` in `bitcoin.conf` match your `.env` |
| Permission errors during scan | Normal — the scanner skips dirs it can't access |

See [README.md](README.md) for full documentation.
