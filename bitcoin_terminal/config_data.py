"""
Bitcoin configuration field definitions.

Comprehensive reference of bitcoin.conf options organized by category,
with descriptions written for clarity and safety warnings where needed.
Supports multiple implementations: Bitcoin Core, Bitcoin Knots, and others.
"""

import re
from typing import Dict, List, Tuple

# Each field: (key, default, type, description, danger_level, impl)
# danger_level: "safe", "caution", "danger"
# type: "bool", "int", "string", "path", "multi" (can appear multiple times)
# impl: "all" = every implementation, "core" = Core only, "knots" = Knots only

SENSITIVE_KEYS = frozenset({
    'rpcpassword', 'rpcauth', 'rpcookie',
})


# ── Implementation detection ───────────────────────────────────────────

# Known implementations and their subversion patterns
IMPLEMENTATIONS = {
    'core':  {'name': 'Bitcoin Core',  'icon': '₿', 'pattern': r'/Satoshi:'},
    'knots': {'name': 'Bitcoin Knots', 'icon': '🪢', 'pattern': r'/Knots:'},
    'btcd':  {'name': 'btcd',          'icon': '⚙', 'pattern': r'/btcd:'},
    'bcoin': {'name': 'bcoin',         'icon': '◉', 'pattern': r'/bcoin:'},
    'libbitcoin': {'name': 'Libbitcoin', 'icon': '▣', 'pattern': r'/libbitcoin:'},
}


def detect_implementation(subversion: str) -> Dict:
    """Detect implementation from the subversion string (from getnetworkinfo).

    Returns dict with: id, name, icon, version, subversion
    """
    for impl_id, info in IMPLEMENTATIONS.items():
        if re.search(info['pattern'], subversion):
            # Extract version number
            ver_match = re.search(r':(\d+\.\d+[\.\d]*)', subversion)
            version = ver_match.group(1) if ver_match else 'unknown'
            return {
                'id': impl_id,
                'name': info['name'],
                'icon': info['icon'],
                'version': version,
                'subversion': subversion,
            }
    # Unknown implementation
    clean = subversion.strip('/')
    return {
        'id': 'unknown',
        'name': clean or 'Unknown',
        'icon': '?',
        'version': '',
        'subversion': subversion,
    }

# ── Field Definitions by Category ──────────────────────────────────────

FIELD_CATEGORIES: Dict[str, List[Tuple[str, str, str, str, str]]] = {

    "🔗 Network": [
        ("listen", "1", "bool",
         "Accept incoming connections from other nodes. "
         "When enabled (1), your node helps the Bitcoin network by relaying "
         "blocks and transactions to peers. Disabling it (0) means you only "
         "connect outward — fine for personal use but doesn't help the network.",
         "safe", "all"),
        ("port", "8333", "int",
         "The port your node listens on for incoming peer-to-peer connections. "
         "The default 8333 is the standard Bitcoin mainnet port. Only change "
         "this if you have a specific reason (e.g., firewall restrictions).",
         "safe", "all"),
        ("bind", "", "string",
         "Bind to a specific IP address for listening. Useful if your machine "
         "has multiple network interfaces and you want to control which one "
         "Bitcoin Core uses for peer connections.",
         "safe", "all"),
        ("externalip", "", "string",
         "Tell other nodes your public IP address. Useful if you're behind NAT "
         "and have set up port forwarding. Helps peers find and connect to you.",
         "safe", "all"),
        ("maxconnections", "125", "int",
         "Maximum number of peer connections (inbound + outbound). Higher means "
         "more network participation but uses more bandwidth and memory. "
         "Setting too low (below 8) may hurt your node's ability to stay synced.",
         "caution", "all"),
        ("maxuploadtarget", "0", "int",
         "Maximum upload bandwidth target in MiB per 24h period. 0 = unlimited. "
         "When set, your node will limit how much data it uploads to peers. "
         "Useful on metered connections. Historical blocks are deprioritized first.",
         "safe", "all"),
        ("maxreceivebuffer", "5000", "int",
         "Maximum per-connection receive buffer size in KB. Rarely needs changing.",
         "safe", "all"),
        ("maxsendbuffer", "1000", "int",
         "Maximum per-connection send buffer size in KB. Rarely needs changing.",
         "safe", "all"),
        ("timeout", "5000", "int",
         "Connection timeout in milliseconds when connecting to a peer. "
         "The default 5 seconds works for most connections.",
         "safe", "all"),
        ("peerbloomfilters", "0", "bool",
         "Allow peers to request bloom filters (BIP 37). Generally left off "
         "for privacy. Only needed if you serve SPV (lightweight) wallets directly.",
         "safe", "all"),
        ("dns", "1", "bool",
         "Allow DNS lookups for finding peers. Disabling means you can only "
         "connect via manually specified IPs or addnode entries.",
         "safe", "all"),
        ("dnsseed", "1", "bool",
         "Query DNS seeds to find initial peers when starting. Safe to leave on. "
         "Disable only if you prefer manual peer management for privacy.",
         "safe", "all"),
        ("seednode", "", "multi",
         "Connect to a specific node to fetch peer addresses, then disconnect. "
         "Used for initial bootstrapping. You can specify multiple seednode entries.",
         "safe", "all"),
        ("addnode", "", "multi",
         "Add a persistent peer node address. Your node will try to maintain "
         "a connection to this peer. Can be specified multiple times.",
         "safe", "all"),
        ("connect", "", "multi",
         "Connect ONLY to specified nodes, ignoring all other peers. "
         "⚠ This isolates your node — use only if you trust these nodes completely. "
         "Can be specified multiple times.",
         "danger", "all"),
        ("whitelist", "", "multi",
         "Give specific permissions to peers matching this IP/netmask. "
         "Whitelisted peers are never banned and can be given relay/mempool privileges.",
         "caution", "all"),
        ("onlynet", "", "multi",
         "Only connect through the specified network (ipv4, ipv6, onion, i2p, cjdns). "
         "Can be specified multiple times to allow multiple networks.",
         "caution", "all"),
        ("proxy", "", "string",
         "Route all connections through a SOCKS5 proxy (e.g., Tor). "
         "Format: ip:port. Common for privacy: 127.0.0.1:9050 (Tor).",
         "safe", "all"),
        ("onion", "", "string",
         "Use a separate SOCKS5 proxy for Tor .onion connections. "
         "Format: ip:port. If not set, uses the general proxy setting.",
         "safe", "all"),
        ("i2psam", "", "string",
         "I2P SAM proxy address for I2P connections. "
         "Format: ip:port. Enables your node to connect over the I2P network.",
         "safe", "all"),
        ("torcontrol", "", "string",
         "Tor control port for creating ephemeral hidden services. "
         "Format: ip:port. Default: 127.0.0.1:9051.",
         "safe", "all"),
        ("torpassword", "", "string",
         "Password for authenticating to Tor control port.",
         "safe", "all"),
        ("natpmp", "0", "bool",
         "Use NAT-PMP to map the listening port on your router automatically. "
         "Convenient if your router supports it.",
         "safe", "all"),
        ("upnp", "0", "bool",
         "Use UPnP to map the listening port on your router. Similar to NAT-PMP. "
         "Some consider UPnP a security risk on untrusted networks.",
         "caution", "all"),
        ("networkactive", "1", "bool",
         "Start with network activity enabled. Set to 0 to start with networking "
         "disabled — useful for offline operations.",
         "safe", "all"),
        ("bantime", "86400", "int",
         "How long (in seconds) misbehaving peers are banned. Default: 24 hours.",
         "safe", "all"),
        ("maxoutconnections", "", "int",
         "Maximum number of outbound connections. Default varies by type.",
         "caution", "all"),
        ("v2transport", "0", "bool",
         "Enable BIP 324 v2 transport protocol for encrypted peer connections. "
         "Improves privacy by encrypting traffic between nodes.",
         "safe", "all"),
    ],

    "⛏ Mining": [
        ("blockmaxweight", "3996000", "int",
         "Maximum block weight your node will generate when mining. "
         "Default is near the 4M weight unit limit. Only relevant if you mine.",
         "safe", "all"),
        ("blockmintxfee", "0.00001000", "string",
         "Minimum fee rate (BTC/kvB) for transactions in generated blocks. "
         "Transactions below this fee rate won't be included in blocks you mine.",
         "safe", "all"),
    ],

    "💰 Wallet": [
        ("disablewallet", "0", "bool",
         "Completely disable the wallet module. Saves memory and startup time "
         "if you only use the node for validation and relay — not for sending BTC.",
         "safe", "all"),
        ("wallet", "", "multi",
         "Name of wallet to load at startup. Can specify multiple. "
         "If not set, the default wallet is loaded.",
         "safe", "all"),
        ("walletdir", "", "path",
         "Directory where wallet files are stored. Default is inside the data directory.",
         "caution", "all"),
        ("addresstype", "bech32", "string",
         "Default address type for new addresses: legacy, p2sh-segwit, or bech32. "
         "bech32 (native SegWit) is recommended for lower fees.",
         "safe", "all"),
        ("changetype", "", "string",
         "Address type for change outputs. Defaults to match addresstype.",
         "safe", "all"),
        ("avoidpartialspends", "0", "bool",
         "Spend all outputs from the same address together. Improves privacy but "
         "may result in slightly higher fees.",
         "safe", "all"),
        ("spendzeroconfchange", "1", "bool",
         "Allow spending unconfirmed change from your own transactions. "
         "Safe because you trust your own change outputs.",
         "safe", "all"),
        ("walletbroadcast", "1", "bool",
         "Broadcast wallet transactions. Set to 0 if you want to relay "
         "transactions through a different method for privacy.",
         "safe", "all"),
        ("walletnotify", "", "string",
         "Execute a command when a wallet transaction is received or updated. "
         "%s is replaced with the txid. Useful for notifications.",
         "caution", "all"),
        ("paytxfee", "0.00000000", "string",
         "Explicit fee rate (BTC/kvB) to use for wallet transactions. "
         "0 = automatic fee estimation (recommended).",
         "caution", "all"),
        ("mintxfee", "0.00001000", "string",
         "Minimum fee rate your wallet will pay. Transactions below this level "
         "are considered 'free' and may not be relayed by the network.",
         "safe", "all"),
        ("maxtxfee", "0.10000000", "string",
         "Maximum total fee your wallet will pay for a single transaction. "
         "A safety limit to prevent accidentally paying absurd fees.",
         "safe", "all"),
        ("fallbackfee", "0.00000000", "string",
         "Fee rate to use when fee estimation has no data (fresh node). "
         "Set conservatively or leave at 0 (transactions fail without estimation).",
         "safe", "all"),
        ("txconfirmtarget", "6", "int",
         "Target number of blocks for fee estimation. Lower = faster confirmation "
         "but higher fee. 6 blocks ≈ ~1 hour is a balanced default.",
         "safe", "all"),
        ("keypool", "1000", "int",
         "Number of pre-generated keys in the key pool. Mainly relevant for "
         "non-HD wallets. Larger pools improve backup resilience.",
         "safe", "all"),
    ],

    "🔌 RPC Server": [
        ("server", "0", "bool",
         "Enable the JSON-RPC server. REQUIRED for this terminal monitor and "
         "any external tool that talks to your node. Set to 1.",
         "safe", "all"),
        ("rpcuser", "", "string",
         "Username for RPC authentication. Needed if you don't use .cookie auth. "
         "Pair with rpcpassword. Avoid simple passwords.",
         "caution", "all"),
        ("rpcpassword", "", "string",
         "Password for RPC authentication. ⚠ Stored in PLAIN TEXT in bitcoin.conf. "
         "For better security, use rpcauth instead. Never reuse important passwords.",
         "danger", "all"),
        ("rpcauth", "", "multi",
         "Hashed RPC credentials (safer than plain rpcpassword). "
         "Format: user:salt$hash. Generate with share/rpcauth/rpcauth.py. "
         "Can specify multiple entries for different users.",
         "safe", "all"),
        ("rpcport", "8332", "int",
         "Port for JSON-RPC connections. Default 8332 for mainnet. "
         "18332 for testnet, 38332 for signet, 18443 for regtest.",
         "safe", "all"),
        ("rpcbind", "127.0.0.1", "string",
         "IP address to bind the RPC server to. Default is localhost only. "
         "⚠ Binding to 0.0.0.0 exposes RPC to the network — very dangerous "
         "without proper firewalling and strong authentication.",
         "danger", "all"),
        ("rpcallowip", "127.0.0.1", "multi",
         "Allow RPC connections from specific IP/subnet. Default: localhost only. "
         "⚠ Opening to external IPs without strong auth is a security risk. "
         "Use with rpcauth and firewall rules.",
         "danger", "all"),
        ("rpcthreads", "4", "int",
         "Number of threads for handling RPC requests. Increase if you have "
         "heavy RPC usage from multiple clients.",
         "safe", "all"),
        ("rpcworkqueue", "16", "int",
         "Maximum depth of the RPC work queue. Increase if you get "
         "'work queue depth exceeded' errors under heavy load.",
         "safe", "all"),
        ("rpcservertimeout", "30", "int",
         "Timeout in seconds for long-poll RPC requests.",
         "safe", "all"),
        ("rpccookiefile", "", "path",
         "Custom location for the .cookie auth file. By default it's in the "
         "data directory. Cookie auth is the easiest and safest RPC auth method.",
         "safe", "all"),
    ],

    "🗄 Storage & Pruning": [
        ("datadir", "", "path",
         "The directory where Bitcoin Core stores all its data: blocks, chainstate, "
         "wallets, and the peer database. Default varies by OS. Moving to an external "
         "drive with lots of space is common.",
         "safe", "all"),
        ("blocksdir", "", "path",
         "Store block files (blocks/*.dat) in a separate directory. "
         "Useful to put the large block data on a different drive than chainstate.",
         "safe", "all"),
        ("prune", "0", "int",
         "Enable block pruning to save disk space. Value is target size in MiB "
         "(minimum 550). Once pruned, your node can't serve old blocks to peers "
         "and can't rescan the full chain. 0 = keep all blocks.\n"
         "⚠ Pruning is IRREVERSIBLE for existing block data. You cannot re-enable "
         "txindex or coinstatsindex on a pruned node.",
         "caution", "all"),
        ("txindex", "0", "bool",
         "Maintain a full transaction index. Allows looking up ANY transaction by txid "
         "(not just wallet transactions). Required by some applications (block explorers). "
         "Uses extra disk space (~30+ GB). Cannot be used with pruning.",
         "safe", "all"),
        ("coinstatsindex", "0", "bool",
         "Maintain a UTXO set statistics index. Enables gettxoutsetinfo with hash_type=muhash "
         "for faster UTXO set queries. Moderate extra disk space.",
         "safe", "all"),
        ("blockfilterindex", "0", "string",
         "Build and maintain compact block filters (BIP 157/158). "
         "Enables serving light clients with block filters. Set to 'basic' or '1'.",
         "safe", "all"),
        ("dbcache", "450", "int",
         "Size of the UTXO database cache in MiB. Higher values dramatically speed up "
         "initial sync and block validation. 450 MB is the default; during IBD, "
         "setting 4000-8000+ (if you have RAM) can 10x sync speed.",
         "safe", "all"),
        ("maxmempool", "300", "int",
         "Maximum mempool size in MiB. When full, transactions with the lowest fee "
         "rate are dropped. 300 MiB is a good default. Reduce on low-memory systems.",
         "safe", "all"),
        ("mempoolexpiry", "336", "int",
         "Remove transactions from mempool after this many hours. "
         "Default: 336 hours (14 days).",
         "safe", "all"),
        ("persistmempool", "1", "bool",
         "Save and reload the mempool on shutdown/startup. Keeps your mempool warm "
         "across restarts — useful for fee estimation accuracy.",
         "safe", "all"),
        ("par", "0", "int",
         "Number of script verification threads. 0 = auto-detect based on CPU cores. "
         "Negative values leave that many cores free. Set 1 to reduce CPU usage.",
         "safe", "all"),
        ("assumevalid", "", "string",
         "Skip script validation for blocks before this hash. Bitcoin Core ships with "
         "a recent hash that's been heavily reviewed. Only change if you distrust the default "
         "or want full from-scratch verification.",
         "caution", "all"),
    ],

    "📡 Relay & Mempool": [
        ("minrelaytxfee", "0.00001000", "string",
         "Minimum fee rate (BTC/kvB) for relaying transactions. Transactions below "
         "this won't be accepted into your mempool or relayed to peers.",
         "safe", "all"),
        ("bytespersigop", "20", "int",
         "Weight units per sigop in relay policy. Affects which transactions your "
         "node relays. Rarely needs changing.",
         "safe", "all"),
        ("datacarrier", "1", "bool",
         "Relay OP_RETURN (data carrier) transactions. These embed small amounts "
         "of data in the blockchain. Disabling rejects them from your mempool.",
         "safe", "all"),
        ("datacarriersize", "83", "int",
         "Maximum size in bytes of OP_RETURN data your node will relay.",
         "safe", "all"),
        ("permitbaremultisig", "1", "bool",
         "Relay bare multisig transactions (not wrapped in P2SH). "
         "Mostly legacy; can be disabled for stricter relay policy.",
         "safe", "all"),
        ("mempoolfullrbf", "1", "bool",
         "Allow full replace-by-fee in the mempool. When enabled, any unconfirmed "
         "transaction can be replaced by one paying a higher fee, even without "
         "the BIP 125 opt-in signal. Default changed to 1 in Bitcoin Core 28.0.",
         "safe", "all"),
        ("acceptnonstdtxn", "0", "bool",
         "Accept non-standard transactions. On mainnet this defaults to 0 "
         "(reject non-standard). On testnet it defaults to 1.",
         "caution", "all"),
    ],

    "🔒 Security": [
        ("disablegovernance", "", "string",
         "Disable specific RPC methods for security.",
         "safe", "all"),
        ("blocksonly", "0", "bool",
         "Only download blocks, not loose transactions. Dramatically reduces "
         "bandwidth (~88% less) but your mempool will be empty and fee estimation "
         "won't work. Your wallet can still send transactions.",
         "caution", "all"),
        ("checkblocks", "6", "int",
         "Number of recent blocks to verify at startup. Higher values increase "
         "startup time but improve confidence in chain integrity.",
         "safe", "all"),
        ("checklevel", "3", "int",
         "How thorough the startup block verification is (0-4). "
         "Level 3 is the default balance of speed and safety.",
         "safe", "all"),
    ],

    "🐛 Debug & Logging": [
        ("debug", "", "multi",
         "Enable debug logging for specific categories: net, tor, mempool, http, "
         "bench, rpc, estimatefee, addrman, selectcoins, reindex, cmpctblock, rand, "
         "prune, proxy, mempoolrej, libevent, coindb, leveldb, validation, i2p, ipc. "
         "Use 'all' for everything. ⚠ 'all' creates huge log files fast.",
         "caution", "all"),
        ("debuglogfile", "debug.log", "path",
         "Location of the debug log file. Default: debug.log in data directory.",
         "safe", "all"),
        ("logtimestamps", "1", "bool",
         "Include timestamps in debug log entries.",
         "safe", "all"),
        ("logips", "0", "bool",
         "Include IP addresses in debug log. Useful for diagnosing network issues "
         "but may be a privacy concern if logs are shared.",
         "caution", "all"),
        ("logtimemicros", "0", "bool",
         "Log timestamps with microsecond precision. Useful for performance profiling.",
         "safe", "all"),
        ("logthreadnames", "0", "bool",
         "Include thread names in debug log. Helpful for debugging Core internals.",
         "safe", "all"),
        ("shrinkdebugfile", "1", "bool",
         "Shrink debug.log on startup if it's over 10MB. Keeps disk usage in check.",
         "safe", "all"),
        ("printtoconsole", "0", "bool",
         "Print debug output to stdout instead of (or in addition to) the log file.",
         "safe", "all"),
        ("alertnotify", "", "string",
         "Execute a command on alerts (like chain forks). %s is replaced with the message. "
         "Useful for monitoring setups.",
         "caution", "all"),
        ("blocknotify", "", "string",
         "Execute a command when a new best block is found. %s = block hash. "
         "Common for triggering indexers or notifications.",
         "caution", "all"),
        ("startupnotify", "", "string",
         "Execute a command when Bitcoin Core has finished startup.",
         "caution", "all"),
    ],

    "🌐 Chain Selection": [
        ("testnet", "0", "bool",
         "Run on testnet3 instead of mainnet. Testnet uses worthless coins for testing. "
         "⚠ Don't mix up mainnet and testnet wallets/data.",
         "caution", "all"),
        ("testnet4", "0", "bool",
         "Run on testnet4 — the newer test network with improved difficulty adjustment.",
         "caution", "all"),
        ("signet", "0", "bool",
         "Run on signet — a centrally-signed test network. More stable than testnet. "
         "Ideal for development and testing.",
         "safe", "all"),
        ("regtest", "0", "bool",
         "Run in regression test mode — a local chain you fully control. "
         "Blocks are mined on demand. Perfect for development.",
         "safe", "all"),
        ("chain", "", "string",
         "Select chain: main, test, testnet4, signet, or regtest. "
         "Alternative to the individual boolean flags above.",
         "caution", "all"),
    ],

    "⚡ Performance": [
        ("maxorphantx", "100", "int",
         "Maximum number of orphan transactions kept in memory. Orphans are "
         "transactions that reference unknown parents.",
         "safe", "all"),
        ("rpcserialversion", "1", "int",
         "Serialization version for RPC output: 0 = non-segwit, 1 = segwit. "
         "Use 1 for modern applications.",
         "safe", "all"),
        ("rest", "0", "bool",
         "Enable the REST interface (HTTP endpoints without auth). "
         "⚠ Only enable if you understand that REST has no authentication. "
         "Bind to localhost only.",
         "caution", "all"),
    ],

    "🧅 Privacy (Tor/I2P)": [
        ("listenonion", "1", "bool",
         "Automatically create a Tor hidden service for inbound connections. "
         "Requires a running Tor instance with control port access. Great for privacy.",
         "safe", "all"),
        ("reach", "", "string",
         "Deprecated option for reachability.",
         "safe", "all"),
    ],
}

# ── Bitcoin Knots–specific options ─────────────────────────────────────
# Knots is a Bitcoin Core fork with extra policy controls.

KNOTS_FIELDS: Dict[str, List[Tuple[str, str, str, str, str, str]]] = {

    "🪢 Knots: Spam Filtering": [
        ("spamfilter", "0", "bool",
         "Enable Knots' built-in spam filter for relay and mempool. "
         "Rejects transactions that carry non-financial data payloads "
         "(inscriptions, BRC-20, etc.). Not available in Bitcoin Core.",
         "caution", "knots"),
        ("rejectparasites", "0", "bool",
         "Reject 'parasite' transactions that abuse OP_RETURN or witness "
         "data for non-monetary purposes. Knots-only policy filter.",
         "caution", "knots"),
        ("datacarrier", "1", "bool",
         "In Knots, this additionally interacts with spamfilter. Setting to 0 "
         "rejects all OP_RETURN outputs. Knots applies stricter data-carrier "
         "rules than Core when spamfilter is also enabled.",
         "safe", "knots"),
        ("datacarriersize", "42", "int",
         "Knots default is 42 bytes (vs Core's 83). Maximum size of OP_RETURN "
         "data your node will relay. Lower values reject more data-embedding txs.",
         "safe", "knots"),
        ("rejectnonstddatacarrier", "1", "bool",
         "Reject non-standard data carrier transactions. Knots-specific option "
         "to enforce stricter relay rules on OP_RETURN usage.",
         "safe", "knots"),
    ],

    "🪢 Knots: Policy Controls": [
        ("permitbaremultisig", "0", "bool",
         "Knots defaults to 0 (reject bare multisig), unlike Core which defaults "
         "to 1. Bare multisig is a legacy pattern rarely used legitimately.",
         "safe", "knots"),
        ("minrelaytxfee", "0.00001000", "string",
         "Knots allows setting this higher to filter low-fee spam. Same as Core "
         "but Knots users often raise it alongside spamfilter.",
         "safe", "knots"),
        ("rejectunknownscripts", "0", "bool",
         "Reject transactions with unrecognized script types. Knots-specific "
         "policy for stricter script validation in mempool.",
         "caution", "knots"),
        ("maxscriptsize", "", "int",
         "Maximum script size (bytes) for relay. Knots option to limit "
         "oversized scripts that may be used for data embedding.",
         "caution", "knots"),
        ("acceptnonstdtxn", "0", "bool",
         "Accept non-standard transactions. Knots keeps this at 0 by default "
         "like Core mainnet, but provides finer-grained control with the "
         "additional spamfilter options above.",
         "caution", "knots"),
    ],

    "🪢 Knots: Mining Policy": [
        ("blockmaxsize", "", "int",
         "Maximum block size in bytes for mining. Knots exposes this option "
         "to let miners set a block size limit below the consensus maximum. "
         "Not available in Bitcoin Core.",
         "caution", "knots"),
        ("blockprioritysize", "0", "int",
         "Reserve space (bytes) in generated blocks for high-priority (old, large) "
         "transactions regardless of fee. Knots retains this option removed from Core.",
         "safe", "knots"),
    ],
}

# Merge Knots fields into main categories dict
for _cat, _fields in KNOTS_FIELDS.items():
    FIELD_CATEGORIES[_cat] = _fields

# Flatten for quick lookup
ALL_FIELDS: Dict[str, Tuple] = {}
FIELD_TO_CATEGORY: Dict[str, str] = {}
for _cat, _fields in FIELD_CATEGORIES.items():
    for _f in _fields:
        ALL_FIELDS[_f[0]] = _f
        FIELD_TO_CATEGORY[_f[0]] = _cat


def get_fields_for_impl(impl_id: str) -> Dict[str, List[Tuple]]:
    """Return only the field categories relevant to the given implementation.

    impl_id: 'core', 'knots', 'unknown', etc.
    Fields tagged 'all' are always included.
    Fields tagged with a specific impl are only included for that impl.
    """
    result: Dict[str, List[Tuple]] = {}
    for cat, fields in FIELD_CATEGORIES.items():
        filtered = [f for f in fields
                    if f[5] == 'all' or f[5] == impl_id]
        if filtered:
            result[cat] = filtered
    return result
