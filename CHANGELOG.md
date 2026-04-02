# Changelog

All notable changes to Bitcoin Terminal will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-beta.5] — 2026-04-02

### Fixed

- **Memory leak — unbounded peer history** — `PeerTracker._peer_history` dict stored every unique peer ever seen and never evicted entries. Now capped at 10,000 with automatic eviction of the oldest stale peers while preserving currently-connected ones
- **Memory leak — unbounded RPC IP history** — `RPCMonitor._rpc_ips` dict accumulated every unique RPC client IP forever. Now capped at 5,000 with stale eviction
- **Expensive list trimming** — Six bounded lists (`_churn_events`, `_conn_snapshots`, `_events`, `_auth_failures`, `_bw_samples`, `_method_counts_1h`) used slice-and-copy trimming (`list = list[-N:]`) which allocated a full copy on every overflow. Converted all to `collections.deque(maxlen=N)` for O(1) append with automatic eviction

---

## [0.1.0-beta.4] — 2026-04-01

### Added

- **Auto-start Bitcoin Core** — On launch, if the node's RPC is unreachable the app now attempts to start `bitcoind` automatically. Searches well-known binary locations per platform (Homebrew, snap, app bundles, Program Files) and falls back to `Bitcoin-Qt -server` if no daemon is found. Waits up to 30 s for the RPC to become reachable, then proceeds to the TUI regardless

---

## [0.1.0-beta.3] — 2026-03-28

### Added

- **"Behind" indicator during sync** — Node card now shows how far behind the network tip the node is in human-readable units (e.g. "3h 12m behind", "2d 5h behind", "1mo 4d behind") using the last synced block's timestamp

### Fixed

- **Total blocks wrong at startup** — Node card showed `blocks / blocks` (e.g. "941,006 / 941,006") instead of the real network tip when Bitcoin Core's header sync hadn't finished yet. Now fetches the network tip from mempool.space as a fallback when `headers <= blocks` during sync
- **Connection error flashing** — Every failed RPC call instantly showed "CONNECTION FAILED" in the node card, causing the UI to flash on transient errors during node startup or heavy sync. Now reuses last-known-good data for up to 6 cycles (~30s) before showing the error state

---

## [0.1.0-beta.2] — 2026-03-15

### Fixed

- **False SYNCED status** — Node showed "SYNCED" while still catching up after restart. Now checks `blocks` vs `headers` gap (>3 blocks behind = SYNCING), not just `verificationprogress` which can read ~100% even hundreds of blocks behind
- **Spurious new-block animations during catch-up** — Every block synced during catch-up triggered the Matrix rain "NEW BLOCK" animation. Now suppressed when node is behind the network tip, not only during Initial Block Download
- **InvalidStateError crash** — `MatrixRainScreen.dismiss()` could fire multiple times from the timer callback, crashing with "invalid state". Added dismiss guard and explicit timer stop to prevent double-dismiss from both timer expiry and key press

---

## [0.1.0-beta.1] — 2026-03-11

First public beta release.

### Added

- **12 Live Dashboard Cards** — Price, Block Height, Node, P2P Peers, Market, Mempool, Blockchain, Halving, RPC Monitor, System Health, Satoshi Quotes — all auto-refreshing
- **Hero Row** — Large ASCII-art BTC price and block height via pyfiglet, responsive fallback for narrow terminals
- **Status Bar** — Sync status, chain, block height, peers, BTC price, hashprice, epoch avg block time, fee % of reward
- **Config Editor** (`c`) — Browse and toggle 112 `bitcoin.conf` fields across 14 categories, danger-level warnings, implementation-aware (Core / Knots / btcd / bcoin)
- **Display Settings** (`s`) — Toggle card visibility, status bar item visibility, and configure figlet font with live preview (24 curated fonts). Persists to `.display_settings.json`
- **Log Viewer** (`l`) — Live `debug.log` tail with color-coded categories, hash truncation, noise filtering
- **Matrix Rain** — Full-screen katakana code rain on new blocks, startup, or on demand (`r`)
- **Setup Wizard** — 7-step guided first-run: auto-detect datadir → scan RPC ports → test connection → configure display
- **One-Line Installer** — `curl -sL https://raw.githubusercontent.com/atlas-ops-bot/bitcoin-terminal/main/install.sh | bash`
- **Auto-Detection** — Finds Bitcoin data directories on macOS / Linux / Windows, cookie auth, external drives
- **Peer Intelligence** — Historical peer tracking, churn detection, bandwidth rates, security alerts
- **RPC Monitor** — Request rates, method frequency, auth failure tracking from `debug.log`
- **Mining Stats** — Hashprice ($/PH/day), fee % of block reward, difficulty adjustment countdown, hashrate ATH & drawdown
- **System Health** — CPU %, temperature, memory, disk usage (root + data drive)
- **Price Data** — CoinGecko primary + mempool.space fallback, disk-cached `.price_cache.json`
- **Responsive Layout** — 3-column (≥120), 2-column (≥80), 1-column (<80) grid with auto-reflow
- **Keyboard Navigation** — `c` config, `l` logs, `s` display settings, `r` rain, `R` refresh, `d` enable RPC debug, `q` quit

### Infrastructure

- Python 3.8+ with Textual TUI framework
- `setup.py` with `bitcoin-terminal` console entry point
- `.env`-based configuration via python-dotenv
- `.gitignore` covering Python, IDE, Bitcoin data, credentials, and AI tool artifacts

---

[0.1.0-beta.5]: https://github.com/atlas-ops-bot/bitcoin-terminal/compare/v0.1.0-beta.4...v0.1.0-beta.5
[0.1.0-beta.4]: https://github.com/atlas-ops-bot/bitcoin-terminal/compare/v0.1.0-beta.3...v0.1.0-beta.4
[0.1.0-beta.3]: https://github.com/atlas-ops-bot/bitcoin-terminal/compare/v0.1.0-beta.2...v0.1.0-beta.3
[0.1.0-beta.2]: https://github.com/atlas-ops-bot/bitcoin-terminal/compare/v0.1.0-beta.1...v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/atlas-ops-bot/bitcoin-terminal/releases/tag/v0.1.0-beta.1
