# Bitcoin Terminal Dashboard 📊

## Overview

The Bitcoin Terminal dashboard provides comprehensive real-time monitoring of your Bitcoin Core node with a beautiful, organized interface.

## Layout

```
╔══════════════════════════════════════════════════════════════════════════╗
║                            BITCOIN                                       ║
║                        Node Monitor v0.1.0                               ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌─────────────────────────┐  ┌─────────────────────────┐              ║
║  │  ⚡ Node Health         │  │  🌐 Network             │              ║
║  ├─────────────────────────┤  ├─────────────────────────┤              ║
║  │ Status       ● SYNCED   │  │ Connections    10       │              ║
║  │ Chain        MAINNET    │  │ Types          IPv4: 8  │              ║
║  │ Block Height 850,000    │  │                Tor: 2   │              ║
║  │ Sync Progress 100.00%   │  │ Traffic ↓      125 MB   │              ║
║  │ Uptime       2d 5h 30m  │  │ Traffic ↑      89 MB    │              ║
║  │ Version      27.0       │  │ Min Relay Fee  1.0 s/vB │              ║
║  │ Disk Usage   650.2 GB   │  │                         │              ║
║  └─────────────────────────┘  └─────────────────────────┘              ║
║                                                                          ║
║  ┌─────────────────────────┐  ┌─────────────────────────┐              ║
║  │  💾 Mempool             │  │  ⛓️  Blockchain          │              ║
║  ├─────────────────────────┤  ├─────────────────────────┤              ║
║  │ Transactions   5,432    │  │ Difficulty     85.45T   │              ║
║  │ Memory Usage   250 MB   │  │ Chain Work     2^208    │              ║
║  │ Total Size     180 MB   │  │ Last Block     5 min    │              ║
║  │ Min Mempool    2.5 s/vB │  │ Best Block     00000... │              ║
║  │ Min Relay      1.0 s/vB │  │                         │              ║
║  └─────────────────────────┘  └─────────────────────────┘              ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐  ║
║  │  ⚙️  Configuration                                                │  ║
║  ├──────────────────────────────────────────────────────────────────┤  ║
║  │  Setting              │ Value                                     │  ║
║  │  ────────────────────┼───────────────────────────────────────── │  ║
║  │  server               │ 1                                         │  ║
║  │  daemon               │ 1                                         │  ║
║  │  prune                │ 0                                         │  ║
║  │  txindex              │ 1                                         │  ║
║  │  rpcuser              │ bitcoin                                   │  ║
║  │  rpcpassword          │ ********                                  │  ║
║  │  rpcport              │ 8332                                      │  ║
║  │  maxconnections       │ 125                                       │  ║
║  │  dbcache              │ 4096                                      │  ║
║  │  ...                  │ ...                                       │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

## Dashboard Cards

### ⚡ Node Health

Shows the overall health and sync status of your Bitcoin node:

- **Status**: Visual indicator (● SYNCED / ⟳ SYNCING / ⟳ CATCHING UP)
- **Chain**: Network type (MAINNET, TESTNET, SIGNET, REGTEST)
- **Block Height**: Current blocks vs total headers
- **Sync Progress**: Verification progress percentage
- **Uptime**: How long the node has been running
- **Version**: Bitcoin Core version
- **Disk Usage**: Total blockchain size on disk
- **Pruning**: Shows if pruning is enabled

**Colors:**
- Green: Node fully synced
- Yellow: Initial Block Download (IBD) in progress
- Blue: Catching up with network

### 🌐 Network

Displays connection and network information:

- **Connections**: Total peers (↓ inbound / ↑ outbound)
- **Connection Types**: Breakdown by protocol
  - IPv4: Standard IPv4 connections
  - IPv6: IPv6 connections
  - Tor: Anonymous Tor connections (shown in magenta)
  - I2P: I2P network connections
- **Traffic**: Network bandwidth usage
  - ↓ Received (in blue)
  - ↑ Sent (in yellow)
- **Min Relay Fee**: Minimum fee to relay transactions

**What to Watch:**
- Healthy nodes typically have 8-125 connections
- Mix of inbound/outbound is good for network health
- Tor connections indicate privacy features are working

### 💾 Mempool

Shows the current state of the transaction memory pool:

- **Transactions**: Number of unconfirmed transactions
- **Memory Usage**: RAM used by mempool (with percentage of max)
- **Total Size**: Size in megabytes
- **Min Mempool Fee**: Minimum fee to enter mempool
- **Min Relay Fee**: Minimum fee to be relayed
- **Unbroadcast**: Transactions not yet broadcast to peers

**What to Watch:**
- High transaction count = network congestion
- Rising mempool fees = higher on-chain costs
- Memory usage near max = mempool is full

### ⛓️ Blockchain

Core blockchain statistics and information:

- **Difficulty**: Current mining difficulty (T = Trillion, B = Billion)
- **Chain Work**: Total accumulated work (in powers of 2)
- **Last Block**: Time since last block was mined
- **Best Block**: Hash of the current chain tip (shortened)
- **Pruning**: Pruning status and target size if enabled

**What to Watch:**
- Difficulty adjusts every 2016 blocks (~2 weeks)
- Last block should be < 10 minutes on average
- Chain work increases with each block

### ⚙️ Configuration

Displays your bitcoin.conf settings in a clean, organized table:

**Security Features:**
- ✅ Passwords and sensitive data are hidden (shown as `********`)
- ✅ Usernames are shown for reference
- ✅ All other settings are displayed

**Important Settings Shown:**
- **server**: RPC server enabled
- **daemon**: Running as daemon
- **prune**: Pruning mode enabled/disabled
- **txindex**: Transaction index enabled
- **rpcuser/rpcpassword**: RPC authentication (password hidden)
- **rpcport/rpcbind**: RPC connection settings
- **port**: P2P network port
- **maxconnections**: Maximum peer connections
- **dbcache**: Database cache size

**Location**: Shows full path to bitcoin.conf at the bottom

## Keyboard Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| `R` | Refresh | Manually refresh all data |
| `C` | Toggle Config | Show/hide configuration card |
| `Q` | Quit | Exit the application |

## Auto-Refresh

The dashboard automatically refreshes every **5 seconds** to show real-time data.

## Color Coding

The dashboard uses intuitive color coding:

- 🟢 **Green**: Good status, success, synced
- 🟡 **Yellow**: Warning, in progress, attention needed
- 🔵 **Blue**: Informational, network data
- 🟣 **Magenta**: Tor connections, privacy features
- 🔴 **Red**: Error, critical issue
- ⚪ **Cyan**: Labels and headers
- ⚫ **Dim**: Less important details

## Node Status Indicators

### ● SYNCED
Your node is fully synchronized with the network. All systems operational.

### ⟳ SYNCING (X.XX%)
Initial Block Download in progress. Your node is downloading the blockchain for the first time.

### ⟳ CATCHING UP (X blocks behind)
Your node is catching up after being offline. Almost there!

## Connection to Bitcoin Core

The dashboard requires:
1. ✅ Bitcoin Core running
2. ✅ RPC enabled in bitcoin.conf
3. ✅ Valid RPC credentials

If Bitcoin Core is not running or RPC is not configured, the Node Health card will show a connection error with helpful information.

## What Makes a Healthy Node?

Look for these indicators:

✅ **Status**: ● SYNCED (green)
✅ **Connections**: 8-125 peers
✅ **Sync Progress**: 100.00%
✅ **Last Block**: < 15 minutes ago
✅ **Mempool**: Reasonable size (< 500 MB)
✅ **Uptime**: Days or weeks of continuous operation

## Troubleshooting

### "Cannot connect to Bitcoin Core"
- Check if Bitcoin Core is running: `bitcoin-cli getblockcount`
- Verify RPC is enabled in bitcoin.conf: `server=1`
- Check RPC credentials match

### "No data shown"
- Wait a few seconds for initial data load
- Press `R` to manually refresh
- Check Bitcoin Core logs: `tail -f ~/.bitcoin/debug.log`

### Configuration card shows "Not found"
- bitcoin.conf doesn't exist
- Create one in your Bitcoin data directory
- See QUICKSTART.md for examples

## Advanced Features

### Pruning Detection
If your node is pruned, the dashboard will show:
- "Pruned" indicator in Node Health
- Target pruning size in GB
- Yellow highlighting

### Network Privacy
Tor and I2P connections are highlighted:
- **Magenta color** for Tor connections
- Shows count of anonymous peers
- Indicates privacy-enhanced operation

### Connection Types
The dashboard breaks down connections by protocol:
- Helps identify network diversity
- Shows if privacy features are working
- Useful for troubleshooting connectivity

---

**Pro Tip**: Keep the dashboard running on a second monitor or in a tmux/screen session to always have visibility into your node's health! 🚀
