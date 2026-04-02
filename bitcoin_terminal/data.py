"""
External data fetchers
Bitcoin price, hashrate, difficulty adjustment via public APIs
System metrics via psutil
P2P peer tracking and RPC connection monitoring
"""

import json
import re
import urllib.request
import urllib.error
import time
import platform
import ctypes
import ctypes.util
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ── API fetchers ───────────────────────────────────────────────────────

def _fetch_json(url: str, timeout: int = 3) -> Optional[Any]:
    """Fetch JSON from URL, return None on failure."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'BitcoinTerminal/0.1',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


# ── Supply & subsidy helpers ────────────────────────────────────────────

MAX_SUPPLY = 21_000_000
HALVING_INTERVAL = 210_000
INITIAL_SUBSIDY = 50  # BTC


def block_subsidy(height: int) -> float:
    """Return the block subsidy in BTC for a given height."""
    halvings = height // HALVING_INTERVAL
    if halvings >= 64:
        return 0.0
    return INITIAL_SUBSIDY / (2 ** halvings)


def total_mined(height: int) -> float:
    """Approximate total BTC mined up to a given block height."""
    mined = 0.0
    h = 0
    subsidy = INITIAL_SUBSIDY
    while h < height and subsidy > 0:
        end = min(h + HALVING_INTERVAL, height)
        blocks_in_era = end - h
        mined += blocks_in_era * subsidy
        h = end
        subsidy /= 2
    return mined


# ── Price cache ─────────────────────────────────────────────────────────
# Persists the last successful CoinGecko response to disk so we can
# enrich mempool.space fallback data with ATH, market cap, and
# inferred 24h change — even across restarts.
_CACHE_FILE = Path(__file__).parent / '.price_cache.json'
_price_cache: Dict[str, Any] = {}


def _load_price_cache() -> Dict[str, Any]:
    """Load cached price data from disk."""
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_price_cache(cache: Dict[str, Any]) -> None:
    """Write price cache to disk."""
    try:
        _CACHE_FILE.write_text(
            json.dumps(cache), encoding='utf-8')
    except OSError:
        pass


# Load on module import
_price_cache = _load_price_cache()


def fetch_price() -> Dict[str, Any]:
    """Fetch BTC price from CoinGecko (has 24h change, market cap, ATH),
    fallback to mempool.space with cached CoinGecko enrichment."""
    global _price_cache

    # CoinGecko /coins/bitcoin — single call gets price, market cap, ATH
    data = _fetch_json(
        'https://api.coingecko.com/api/v3/coins/bitcoin'
        '?localization=false&tickers=false&community_data=false'
        '&developer_data=false&sparkline=false',
        timeout=8,
    )
    if data and 'market_data' in data:
        md = data['market_data']
        result: Dict[str, Any] = {
            'usd': md.get('current_price', {}).get('usd', 0),
            'usd_24h_change': md.get('price_change_percentage_24h', 0),
            'usd_market_cap': md.get('market_cap', {}).get('usd', 0),
            'source': 'coingecko',
        }
        ath_usd = md.get('ath', {}).get('usd', 0)
        if ath_usd:
            result['ath_usd'] = ath_usd
            result['ath_date'] = md.get('ath_date', {}).get('usd', '')
            result['ath_change_pct'] = md.get(
                'ath_change_percentage', {}).get('usd', 0)
        # Cache for fallback enrichment
        _price_cache = {
            'usd': result['usd'],
            'ts': time.time(),
            'usd_24h_change': result.get('usd_24h_change', 0),
            'ath_usd': result.get('ath_usd', 0),
            'ath_date': result.get('ath_date', ''),
            'usd_market_cap': result.get('usd_market_cap', 0),
        }
        _save_price_cache(_price_cache)
        return result

    # Fallback: mempool.space — enrich with cached CoinGecko data
    data = _fetch_json('https://mempool.space/api/v1/prices')
    if data and 'USD' in data:
        usd = data['USD']
        result = {
            'usd': usd,
            'source': 'mempool.space',
        }

        # Enrich from cache
        if _price_cache:
            # ATH is stable — carry forward as-is
            if _price_cache.get('ath_usd'):
                result['ath_usd'] = _price_cache['ath_usd']
                result['ath_date'] = _price_cache.get('ath_date', '')
                # Recompute ATH decline from current price
                result['ath_change_pct'] = (
                    (usd - _price_cache['ath_usd'])
                    / _price_cache['ath_usd'] * 100
                )

            # Infer 24h change from cached price + timestamp
            cached_usd = _price_cache.get('usd', 0)
            cached_ts = _price_cache.get('ts', 0)
            if cached_usd > 0 and cached_ts > 0:
                result['usd_24h_change'] = (
                    (usd - cached_usd) / cached_usd * 100
                )

            # Market cap: scale cached cap by price ratio
            cached_mcap = _price_cache.get('usd_market_cap', 0)
            if cached_mcap > 0 and cached_usd > 0:
                result['usd_market_cap'] = cached_mcap * (usd / cached_usd)

        return result

    # Total failure — return cache if recent (< 5 min)
    if _price_cache and (time.time() - _price_cache.get('ts', 0)) < 300:
        return {
            'usd': _price_cache['usd'],
            'usd_24h_change': _price_cache.get('usd_24h_change', 0),
            'source': 'cached',
            'ath_usd': _price_cache.get('ath_usd', 0),
            'ath_date': _price_cache.get('ath_date', ''),
            'ath_change_pct': (
                (_price_cache['usd'] - _price_cache.get('ath_usd', 0))
                / _price_cache['ath_usd'] * 100
            ) if _price_cache.get('ath_usd') else 0,
            'usd_market_cap': _price_cache.get('usd_market_cap', 0),
        }

    return {}


# ── Network tip cache ──────────────────────────────────────────────────
# Stores the last known network tip height from mempool.space so we can
# show accurate total blocks even before Bitcoin Core's header sync
# finishes after a restart.
_network_tip_height: int = 0
_network_tip_ts: float = 0.0


def fetch_network_tip() -> int:
    """Fetch current network tip height from mempool.space.

    Caches the result for 60 seconds to avoid hammering the API.
    Returns cached value on failure.
    """
    global _network_tip_height, _network_tip_ts
    now = time.time()
    if _network_tip_height > 0 and (now - _network_tip_ts) < 60:
        return _network_tip_height
    data = _fetch_json('https://mempool.space/api/blocks/tip/height',
                       timeout=3)
    if isinstance(data, int) and data > 0:
        _network_tip_height = data
        _network_tip_ts = now
    return _network_tip_height


def fetch_difficulty_adjustment() -> Dict[str, Any]:
    """Fetch difficulty adjustment data from mempool.space."""
    data = _fetch_json('https://mempool.space/api/v1/difficulty-adjustment')
    if data:
        return {
            'progress': data.get('progressPercent', 0),
            'change': data.get('difficultyChange', 0),
            'estimated_retarget': data.get('estimatedRetargetDate', 0),
            'remaining_blocks': data.get('remainingBlocks', 0),
            'remaining_time': data.get('remainingTime', 0),
            'previous_retarget': data.get('previousRetarget', 0),
            'next_retarget_height': data.get('nextRetargetHeight', 0),
        }
    return {}


def fetch_hashrate() -> Dict[str, Any]:
    """Fetch network hashrate from mempool.space."""
    data = _fetch_json('https://mempool.space/api/v1/mining/hashrate/1m')
    if data and 'currentHashrate' in data:
        result = {
            'hashrate': data['currentHashrate'],
            'difficulty': data.get('currentDifficulty', 0),
        }
        # Derive ATH from historical data
        hr_list = data.get('hashrates', [])
        if hr_list:
            ath = max(h.get('avgHashrate', 0) for h in hr_list)
            if ath > 0:
                result['hashrate_ath'] = ath
        return result
    return {}


def fetch_recommended_fees() -> Dict[str, Any]:
    """Fetch recommended fee rates from mempool.space."""
    data = _fetch_json('https://mempool.space/api/v1/fees/recommended')
    if data:
        return {
            'fastest': data.get('fastestFee', 0),
            'half_hour': data.get('halfHourFee', 0),
            'hour': data.get('hourFee', 0),
            'economy': data.get('economyFee', 0),
            'minimum': data.get('minimumFee', 0),
        }
    return {}


# ── System metrics ─────────────────────────────────────────────────────

def _macos_cpu_temp() -> Optional[float]:
    """Read CPU die temperature on macOS via IOHIDEventSystemClient."""
    if platform.system() != 'Darwin':
        return None
    try:
        iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library('IOKit'))
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreFoundation'))

        iokit.IOHIDEventSystemClientCreate.restype = ctypes.c_void_p
        iokit.IOHIDEventSystemClientCreate.argtypes = [ctypes.c_void_p]
        client = iokit.IOHIDEventSystemClientCreate(0)
        if not client:
            return None

        iokit.IOHIDEventSystemClientCopyServices.restype = ctypes.c_void_p
        iokit.IOHIDEventSystemClientCopyServices.argtypes = [ctypes.c_void_p]
        services = iokit.IOHIDEventSystemClientCopyServices(client)
        if not services:
            return None

        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]

        iokit.IOHIDServiceClientCopyProperty.restype = ctypes.c_void_p
        iokit.IOHIDServiceClientCopyProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p]
        iokit.IOHIDServiceClientCopyEvent.restype = ctypes.c_void_p
        iokit.IOHIDServiceClientCopyEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_int64, ctypes.c_int32, ctypes.c_int64]
        iokit.IOHIDEventGetFloatValue.restype = ctypes.c_double
        iokit.IOHIDEventGetFloatValue.argtypes = [
            ctypes.c_void_p, ctypes.c_int32]

        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFRelease.argtypes = [ctypes.c_void_p]

        kCFStringEncodingUTF8 = 0x08000100
        kIOHIDEventTypeTemperature = 15
        product_key = cf.CFStringCreateWithCString(
            None, b'Product', kCFStringEncodingUTF8)

        count = cf.CFArrayGetCount(services)
        die_temps = []

        for i in range(count):
            sc = cf.CFArrayGetValueAtIndex(services, i)
            if not sc:
                continue
            name_cf = iokit.IOHIDServiceClientCopyProperty(sc, product_key)
            if not name_cf:
                continue
            buf = ctypes.create_string_buffer(256)
            ok = cf.CFStringGetCString(
                name_cf, buf, 256, kCFStringEncodingUTF8)
            cf.CFRelease(name_cf)
            if not ok:
                continue
            name = buf.value.decode('utf-8', errors='replace')

            event = iokit.IOHIDServiceClientCopyEvent(
                sc, kIOHIDEventTypeTemperature, 0, 0)
            if not event:
                continue
            temp = iokit.IOHIDEventGetFloatValue(
                event, kIOHIDEventTypeTemperature << 16)
            cf.CFRelease(event)

            if 0 < temp < 130 and 'tdie' in name.lower():
                die_temps.append(temp)

        cf.CFRelease(product_key)
        cf.CFRelease(services)

        if die_temps:
            return sum(die_temps) / len(die_temps)
        return None
    except Exception:
        return None


def fetch_system_metrics(datadir: Optional[str] = None) -> Dict[str, Any]:
    """Get CPU, memory, disk usage, and data drive usage."""
    if not HAS_PSUTIL:
        return {}

    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot = psutil.boot_time()

        # CPU temperature (platform-dependent)
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name in ('coretemp', 'cpu_thermal',
                             'cpu-thermal', 'k10temp',
                             'zenpower', 'acpitz'):
                    if name in temps and temps[name]:
                        cpu_temp = temps[name][0].current
                        break
                if cpu_temp is None:
                    first = next(iter(temps.values()), [])
                    if first:
                        cpu_temp = first[0].current
        except (AttributeError, OSError, NotImplementedError):
            pass

        # macOS fallback: read from IOHIDEventSystemClient
        if cpu_temp is None:
            cpu_temp = _macos_cpu_temp()

        result = {
            'cpu_percent': cpu_pct,
            'cpu_temp': cpu_temp,
            'mem_total': mem.total,
            'mem_used': mem.used,
            'mem_percent': mem.percent,
            'boot_time': boot,
        }

        # Primary disk: Bitcoin data dir if available, else /
        if datadir:
            try:
                data_disk = psutil.disk_usage(datadir)
                result['disk_total'] = data_disk.total
                result['disk_used'] = data_disk.used
                result['disk_percent'] = data_disk.percent
                result['disk_label'] = datadir
                # Secondary: root / if it's a different volume
                if data_disk.total != disk.total:
                    result['root_disk_total'] = disk.total
                    result['root_disk_used'] = disk.used
                    result['root_disk_percent'] = disk.percent
            except (OSError, FileNotFoundError):
                result['disk_total'] = disk.total
                result['disk_used'] = disk.used
                result['disk_percent'] = disk.percent
                result['disk_label'] = '/'
        else:
            result['disk_total'] = disk.total
            result['disk_used'] = disk.used
            result['disk_percent'] = disk.percent
            result['disk_label'] = '/'

        return result
    except (OSError, AttributeError):
        return {}


# ── Sync ETA ───────────────────────────────────────────────────────────

class SyncTracker:
    """Track sync progress and estimate ETA."""

    def __init__(self):
        self._samples: list = []
        self._max_samples = 30  # ~2.5 min at 5s intervals

    def update(self, blocks: int, headers: int) -> Dict[str, Any]:
        """Add a sample and compute ETA."""
        now = time.time()

        # Detect reorg: if blocks decreased, reset samples
        if self._samples and blocks < self._samples[-1][1]:
            self._samples.clear()

        self._samples.append((now, blocks))

        # Keep only recent samples
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples:]

        remaining = headers - blocks
        if remaining <= 0:
            return {'remaining': 0, 'eta_seconds': 0, 'blocks_per_sec': 0}

        # Need at least 2 samples to compute rate
        if len(self._samples) < 2:
            return {'remaining': remaining, 'eta_seconds': 0, 'blocks_per_sec': 0}

        first_time, first_blocks = self._samples[0]
        elapsed = now - first_time
        blocks_synced = blocks - first_blocks

        if elapsed <= 0 or blocks_synced <= 0:
            return {'remaining': remaining, 'eta_seconds': 0, 'blocks_per_sec': 0}

        rate = blocks_synced / elapsed  # blocks per second
        eta = remaining / rate

        return {
            'remaining': remaining,
            'eta_seconds': int(eta),
            'blocks_per_sec': rate,
        }


def format_hashrate(hashrate: float) -> str:
    """Format hashrate to human readable."""
    if hashrate >= 1e18:
        return f"{hashrate/1e18:.1f} EH/s"
    elif hashrate >= 1e15:
        return f"{hashrate/1e15:.1f} PH/s"
    elif hashrate >= 1e12:
        return f"{hashrate/1e12:.1f} TH/s"
    elif hashrate >= 1e9:
        return f"{hashrate/1e9:.1f} GH/s"
    else:
        return f"{hashrate:.0f} H/s"


def format_eta(seconds: int) -> str:
    """Format ETA seconds to human readable."""
    if seconds <= 0:
        return "calculating..."
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0:
        return f"~{days}d {hours}h"
    elif hours > 0:
        return f"~{hours}h {mins}m"
    else:
        return f"~{mins}m"


# ── Connection Tracker ─────────────────────────────────────────────────

def _peer_key(peer: Dict) -> str:
    """Unique key for a peer: addr + subver to distinguish nodes."""
    return f"{peer.get('addr', 'unknown')}|{peer.get('subver', '')}"


def _classify_network(peer: Dict) -> str:
    """Classify a peer's network type."""
    addr = peer.get('addr', '')
    nt = peer.get('network', '')
    if nt == 'onion' or '.onion' in addr:
        return 'tor'
    elif nt == 'i2p' or '.b32.i2p' in addr:
        return 'i2p'
    elif addr.startswith('[') or addr.count(':') > 1:
        return 'ipv6'
    return 'ipv4'


class PeerTracker:
    """Track P2P network peers over time for performance and security.

    Records peer snapshots on every refresh and computes:
    - Unique peers seen: last 1h, last 24h, all-time
    - Peak / min / avg peer counts
    - New connections and disconnections per hour (churn)
    - Bandwidth rates (bytes/sec)
    - Average peer connection duration
    - Per-network-type historical stats (IPv4/IPv6/Tor/I2P)
    - Security flags (rapid churn, unusual inbound spikes)
    """

    _MAX_PEER_HISTORY = 10_000  # cap unique peers tracked

    def __init__(self):
        self._start_time: float = time.time()

        # Historical peer records: {peer_key: {first_seen, last_seen, network, inbound}}
        self._peer_history: Dict[str, Dict[str, Any]] = {}

        # Snapshots of connection counts over time: [(timestamp, total, in, out)]
        self._conn_snapshots: deque = deque(maxlen=17_280)  # ~24h at 5s intervals

        # Bandwidth tracking for rate calculation
        self._bw_samples: deque = deque(maxlen=12)  # ~1 min of samples for rate

        # Current peer set (keys) for churn detection
        self._prev_peer_keys: Set[str] = set()

        # Churn events: [(timestamp, 'connect'|'disconnect')]
        self._churn_events: deque = deque(maxlen=50_000)

        # Security alerts
        self._alerts: List[Dict[str, Any]] = []

    def update(self, peers: list, network: Dict) -> Dict[str, Any]:
        """Process a new peer snapshot and return connection stats."""
        now = time.time()

        # Build current peer set
        current_keys: Set[str] = set()
        for peer in peers:
            key = _peer_key(peer)
            current_keys.add(key)

            if key not in self._peer_history:
                self._peer_history[key] = {
                    'first_seen': now,
                    'last_seen': now,
                    'network': _classify_network(peer),
                    'inbound': peer.get('inbound', False),
                    'subver': peer.get('subver', ''),
                    'addr': peer.get('addr', ''),
                    'conntime': peer.get('conntime', 0),
                }
            else:
                self._peer_history[key]['last_seen'] = now

        # Detect churn
        new_peers = current_keys - self._prev_peer_keys
        dropped_peers = self._prev_peer_keys - current_keys
        for _ in new_peers:
            self._churn_events.append((now, 'connect'))
        for _ in dropped_peers:
            self._churn_events.append((now, 'disconnect'))
        self._prev_peer_keys = current_keys

        # Evict stale peers when history exceeds cap
        if len(self._peer_history) > self._MAX_PEER_HISTORY:
            self._evict_stale_peers(now)

        # Record connection snapshot
        total = network.get('connections', len(peers))
        conn_in = network.get('connections_in', 0)
        conn_out = network.get('connections_out', 0)
        self._conn_snapshots.append((now, total, conn_in, conn_out))

        # Bandwidth sample
        total_rx = sum(p.get('bytesrecv', 0) for p in peers)
        total_tx = sum(p.get('bytessent', 0) for p in peers)
        self._bw_samples.append((now, total_rx, total_tx))

        # Security checks
        self._check_security(now, conn_in, total)

        return self._build_stats(now, peers)

    def _evict_stale_peers(self, now: float):
        """Remove oldest peers to keep history within cap."""
        # Keep currently-connected + most-recently-seen entries
        keep = self._MAX_PEER_HISTORY * 3 // 4
        sorted_keys = sorted(
            self._peer_history,
            key=lambda k: self._peer_history[k]['last_seen'],
        )
        to_remove = len(sorted_keys) - keep
        if to_remove > 0:
            # Never remove currently-connected peers
            for key in sorted_keys[:to_remove]:
                if key not in self._prev_peer_keys:
                    del self._peer_history[key]

    def _check_security(self, now: float,
                        conn_in: int, total: int):
        """Check for suspicious connection patterns."""
        self._alerts = []

        # High churn: >20 new connections in the last 5 minutes
        five_min_ago = now - 300
        recent_connects = sum(
            1 for ts, ev in self._churn_events
            if ts > five_min_ago and ev == 'connect'
        )
        if recent_connects > 20:
            self._alerts.append({
                'level': 'warning',
                'msg': f'High churn: {recent_connects} new peers in 5m',
            })

        # Inbound spike: inbound > 80% of total and total > 20
        if total > 20 and conn_in > 0:
            inbound_ratio = conn_in / total
            if inbound_ratio > 0.80:
                self._alerts.append({
                    'level': 'warning',
                    'msg': f'Inbound heavy: {conn_in}/{total} '
                           f'({inbound_ratio:.0%})',
                })

    def _build_stats(self, now: float, peers: list) -> Dict[str, Any]:
        """Build comprehensive connection statistics."""
        one_hour_ago = now - 3600
        twenty_four_ago = now - 86400

        # Unique peers by time window
        unique_1h = set()
        unique_24h = set()
        unique_all = set(self._peer_history.keys())

        for key, info in self._peer_history.items():
            if info['last_seen'] >= one_hour_ago:
                unique_1h.add(key)
            if info['last_seen'] >= twenty_four_ago:
                unique_24h.add(key)

        # Connection count stats from snapshots
        if self._conn_snapshots:
            counts = [s[1] for s in self._conn_snapshots]
            peak = max(counts)
            minimum = min(counts)
            avg = sum(counts) / len(counts)

            # 24h / 1h subsets
            counts_24h = [s[1] for s in self._conn_snapshots
                          if s[0] >= twenty_four_ago]
            counts_1h = [s[1] for s in self._conn_snapshots
                         if s[0] >= one_hour_ago]
            peak_24h = max(counts_24h) if counts_24h else peak
            peak_1h = max(counts_1h) if counts_1h else peak
            avg_24h = (sum(counts_24h) / len(counts_24h)) if counts_24h else avg
        else:
            peak = minimum = avg = peak_24h = peak_1h = avg_24h = 0

        # Churn rates (per hour)
        connects_1h = sum(
            1 for ts, ev in self._churn_events
            if ts >= one_hour_ago and ev == 'connect'
        )
        disconnects_1h = sum(
            1 for ts, ev in self._churn_events
            if ts >= one_hour_ago and ev == 'disconnect'
        )
        connects_24h = sum(
            1 for ts, ev in self._churn_events
            if ts >= twenty_four_ago and ev == 'connect'
        )
        disconnects_24h = sum(
            1 for ts, ev in self._churn_events
            if ts >= twenty_four_ago and ev == 'disconnect'
        )

        # Bandwidth rates
        rx_rate = tx_rate = 0.0
        if len(self._bw_samples) >= 2:
            first_ts, first_rx, first_tx = self._bw_samples[0]
            last_ts, last_rx, last_tx = self._bw_samples[-1]
            elapsed = last_ts - first_ts
            if elapsed > 0:
                rx_rate = (last_rx - first_rx) / elapsed
                tx_rate = (last_tx - first_tx) / elapsed

        # Average connection duration (from conntime of current peers)
        durations = []
        for peer in peers:
            conntime = peer.get('conntime', 0)
            if conntime > 0:
                durations.append(now - conntime)
        avg_duration = (sum(durations) / len(durations)) if durations else 0

        # Longest connection
        max_duration = max(durations) if durations else 0

        # Per-network historical stats
        net_counts: Dict[str, int] = defaultdict(int)
        net_counts_24h: Dict[str, int] = defaultdict(int)
        for key, info in self._peer_history.items():
            net_counts[info['network']] += 1
            if info['last_seen'] >= twenty_four_ago:
                net_counts_24h[info['network']] += 1

        # Inbound vs outbound ratio from current snapshot
        current_in = 0
        current_out = 0
        for peer in peers:
            if peer.get('inbound', False):
                current_in += 1
            else:
                current_out += 1

        uptime_secs = now - self._start_time

        return {
            # Unique peer counts
            'unique_1h': len(unique_1h),
            'unique_24h': len(unique_24h),
            'unique_all': len(unique_all),
            # Connection stats
            'peak': peak,
            'peak_1h': peak_1h,
            'peak_24h': peak_24h,
            'minimum': minimum,
            'avg': avg,
            'avg_24h': avg_24h,
            # Churn
            'connects_1h': connects_1h,
            'disconnects_1h': disconnects_1h,
            'connects_24h': connects_24h,
            'disconnects_24h': disconnects_24h,
            # Bandwidth rates (bytes/sec)
            'rx_rate': rx_rate,
            'tx_rate': tx_rate,
            # Connection duration
            'avg_duration': avg_duration,
            'max_duration': max_duration,
            # Per-network historical
            'net_history': dict(net_counts),
            'net_history_24h': dict(net_counts_24h),
            # Inbound/outbound current
            'inbound': current_in,
            'outbound': current_out,
            # Tracker uptime
            'tracker_uptime': uptime_secs,
            # Security
            'alerts': list(self._alerts),
        }


# ── RPC Connection Monitor ─────────────────────────────────────────────

# Bitcoin Core debug.log patterns for RPC/HTTP activity.
# These appear when debug=http or debug=rpc is set in bitcoin.conf,
# but some messages appear unconditionally (auth failures, startup).

# "Accepting HTTP connection from <ip>:<port>" (older Core)
# "[http] Received a POST request for / from <ip>:<port>" (v25+)
_RPC_ACCEPT_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z'
    r'.*(?:Accepting HTTP connection.*?from'
    r'|\[http\] Received a (?:POST|GET) request for \S+ from)\s+(\S+)',
    re.IGNORECASE,
)
# "ThreadRPCServer method=<method>" (debug=rpc, older Core)
_RPC_METHOD_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z'
    r'.*ThreadRPCServer\s+method=(\S+)',
)
# "HTTP: Closing connection" / "[http] Closing" (debug=http)
_RPC_CLOSE_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z'
    r'.*(?:HTTP.*Closing|\[http\].*Clos)',
    re.IGNORECASE,
)
# Authentication failure (always logged, no debug= needed)
_RPC_AUTH_FAIL_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z'
    r'.*(?:ThreadRPCServer.*incorrect.*password'
    r'|HTTP.*401'
    r'|\[http\].*401)',
    re.IGNORECASE,
)


def _parse_log_ts(ts_str: str) -> float:
    """Parse '2026-03-07T11:12:44' (UTC from debug.log) to epoch seconds."""
    try:
        from datetime import datetime, timezone
        dt = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S')
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, OSError):
        return 0.0


class RPCMonitor:
    """Monitor RPC/HTTP connections by parsing Bitcoin Core debug.log.

    Tracks:
    - Total RPC connections accepted (1h, 24h, all-time)
    - Unique RPC client IPs
    - RPC methods called + frequency
    - Authentication failures (security)
    - Active / closed connection counts
    - Connection rate (per minute)

    Note: Full data requires `debug=http` and/or `debug=rpc` in
    bitcoin.conf. Without those, only auth failures are tracked.
    """

    _MAX_RPC_IPS = 5_000  # cap unique IPs tracked

    def __init__(self, log_path: Optional[Path] = None):
        self._log_path = log_path
        self._file_pos: int = 0  # seek position for incremental reads
        self._initialized: bool = False

        # Events: [(epoch, event_type, detail)]
        self._events: deque = deque(maxlen=100_000)

        # Unique IPs that connected via RPC
        self._rpc_ips: Dict[str, Dict[str, Any]] = {}

        # RPC method call counts
        self._method_counts: Dict[str, int] = defaultdict(int)
        self._method_counts_1h: deque = deque(maxlen=100_000)

        # Auth failures: [(ts, detail)]
        self._auth_failures: deque = deque(maxlen=10_000)

        # Connection counts
        self._total_accepted: int = 0
        self._total_closed: int = 0

        # Security alerts
        self._alerts: List[Dict[str, Any]] = []

    def set_log_path(self, path: Optional[Path]):
        """Set or update the log path."""
        if path != self._log_path:
            self._log_path = path
            self._file_pos = 0
            self._initialized = False

    def update(self) -> Dict[str, Any]:
        """Read new log lines and return RPC connection stats."""
        now = time.time()
        self._read_new_lines()
        return self._build_stats(now)

    def _read_new_lines(self):
        """Read new lines from debug.log since last position."""
        if not self._log_path or not self._log_path.exists():
            return

        try:
            file_size = self._log_path.stat().st_size
        except OSError:
            return

        # On first read, scan last ~1MB to catch recent HTTP entries
        if not self._initialized:
            self._initialized = True
            start_pos = max(0, file_size - 1_048_576)
            self._file_pos = start_pos

        # File was truncated/rotated
        if file_size < self._file_pos:
            self._file_pos = 0

        if file_size <= self._file_pos:
            return

        try:
            with open(self._log_path, 'r',
                       encoding='utf-8', errors='replace') as f:
                f.seek(self._file_pos)
                # Read remaining bytes (up to 1MB per cycle)
                to_read = min(file_size - self._file_pos, 1_048_576)
                chunk = f.read(to_read)
                self._file_pos = f.tell()
        except (OSError, IOError):
            return

        for line in chunk.splitlines():
            self._parse_line(line)

    def _parse_line(self, line: str):
        """Parse a single log line for RPC events."""
        # HTTP connection accepted
        m = _RPC_ACCEPT_RE.search(line)
        if m:
            ts = _parse_log_ts(m.group(1))
            if ts <= 0:
                return
            raw_ip = m.group(2)
            # Strip port (127.0.0.1:51455 → 127.0.0.1)
            ip = raw_ip.rsplit(':', 1)[0] if ':' in raw_ip else raw_ip
            self._total_accepted += 1
            self._events.append((ts, 'accept', ip))
            if ip not in self._rpc_ips:
                self._rpc_ips[ip] = {
                    'first_seen': ts, 'last_seen': ts, 'count': 1
                }
            else:
                self._rpc_ips[ip]['last_seen'] = ts
                self._rpc_ips[ip]['count'] += 1
            self._evict_stale_ips()
            return

        # RPC method call
        m = _RPC_METHOD_RE.search(line)
        if m:
            ts = _parse_log_ts(m.group(1))
            if ts <= 0:
                return
            method = m.group(2)
            self._method_counts[method] += 1
            self._method_counts_1h.append((ts, method))
            self._events.append((ts, 'method', method))
            return

        # Connection closed
        m = _RPC_CLOSE_RE.search(line)
        if m:
            ts = _parse_log_ts(m.group(1))
            if ts <= 0:
                return
            self._total_closed += 1
            self._events.append((ts, 'close', ''))
            return

        # Auth failure
        m = _RPC_AUTH_FAIL_RE.search(line)
        if m:
            ts_str = m.group(1)
            ts = _parse_log_ts(ts_str) if ts_str else time.time()
            self._auth_failures.append((ts, line.strip()[:200]))
            self._events.append((ts, 'auth_fail', ''))

    def _evict_stale_ips(self):
        """Remove oldest IPs when history exceeds cap."""
        if len(self._rpc_ips) <= self._MAX_RPC_IPS:
            return
        keep = self._MAX_RPC_IPS * 3 // 4
        sorted_ips = sorted(
            self._rpc_ips,
            key=lambda k: self._rpc_ips[k]['last_seen'],
        )
        for ip in sorted_ips[:len(sorted_ips) - keep]:
            del self._rpc_ips[ip]

    def _build_stats(self, now: float) -> Dict[str, Any]:
        """Build RPC connection statistics."""
        one_hour_ago = now - 3600
        twenty_four_ago = now - 86400

        # Filter method calls list for 1h window
        filtered = deque(
            ((ts, m) for ts, m in self._method_counts_1h
             if ts >= one_hour_ago),
            maxlen=self._method_counts_1h.maxlen,
        )
        self._method_counts_1h = filtered

        # Connections by time window
        accepts_1h = sum(
            1 for ts, ev, _ in self._events
            if ts >= one_hour_ago and ev == 'accept'
        )
        accepts_24h = sum(
            1 for ts, ev, _ in self._events
            if ts >= twenty_four_ago and ev == 'accept'
        )

        # Unique IPs by window
        ips_1h = set()
        ips_24h = set()
        ips_all = set(self._rpc_ips.keys())
        for ip, info in self._rpc_ips.items():
            if info['last_seen'] >= one_hour_ago:
                ips_1h.add(ip)
            if info['last_seen'] >= twenty_four_ago:
                ips_24h.add(ip)

        # Auth failures by window
        auth_fails_1h = sum(
            1 for ts, _ in self._auth_failures
            if ts >= one_hour_ago
        )
        auth_fails_24h = sum(
            1 for ts, _ in self._auth_failures
            if ts >= twenty_four_ago
        )
        auth_fails_all = len(self._auth_failures)

        # Recent auth failure details (last 5)
        n = len(self._auth_failures)
        start = max(0, n - 5)
        recent_auth_fails = [
            self._auth_failures[i][1] for i in range(start, n)
        ]

        # Top RPC methods (all time)
        top_methods = sorted(
            self._method_counts.items(),
            key=lambda x: x[1], reverse=True
        )[:8]

        # Methods called in last hour
        methods_1h: Dict[str, int] = defaultdict(int)
        for ts, method in self._method_counts_1h:
            methods_1h[method] += 1
        total_calls_1h = sum(methods_1h.values())

        # Connection rate (per minute, last 5 min)
        five_min_ago = now - 300
        recent_accepts = sum(
            1 for ts, ev, _ in self._events
            if ts >= five_min_ago and ev == 'accept'
        )
        conn_rate_per_min = recent_accepts / 5.0 if recent_accepts else 0

        # Security checks
        self._alerts = []
        if auth_fails_1h > 0:
            self._alerts.append({
                'level': 'warning',
                'msg': f'{auth_fails_1h} auth failure(s) in 1h',
            })
        if auth_fails_1h > 10:
            self._alerts.append({
                'level': 'critical',
                'msg': 'Possible brute-force: '
                       f'{auth_fails_1h} failures in 1h',
            })
        # Only alert on high rate from non-localhost sources
        non_local_rate = 0
        if conn_rate_per_min > 0:
            non_local_recent = sum(
                1 for ts, ev, detail in self._events
                if ts >= five_min_ago and ev == 'accept'
                and detail not in ('127.0.0.1', '::1', 'localhost')
            )
            non_local_rate = non_local_recent / 5.0
        if non_local_rate > 20:
            self._alerts.append({
                'level': 'warning',
                'msg': f'High external RPC rate: '
                       f'{non_local_rate:.0f}/min',
            })
        # Unknown IPs in last hour
        unknown_ips_1h = set()
        for ip in ips_1h:
            # Localhost variants are expected
            if ip not in ('127.0.0.1', '::1', 'localhost',
                          '127.0.0.1:8332'):
                stripped = ip.split(':')[0] if ':' in ip else ip
                if stripped not in ('127.0.0.1', '::1', 'localhost'):
                    unknown_ips_1h.add(ip)
        if unknown_ips_1h:
            self._alerts.append({
                'level': 'warning',
                'msg': f'Non-local RPC from: '
                       f'{", ".join(list(unknown_ips_1h)[:3])}',
            })

        has_data = (self._total_accepted > 0
                    or auth_fails_all > 0
                    or len(self._method_counts) > 0)

        # Top client IPs by connection count
        top_ips = sorted(
            self._rpc_ips.items(),
            key=lambda x: x[1]['count'], reverse=True
        )[:5]

        # Last connection timestamp
        last_conn_ts = 0.0
        for ts, ev, _ in reversed(self._events):
            if ev == 'accept':
                last_conn_ts = ts
                break

        return {
            # Connection counts
            'total_accepted': self._total_accepted,
            'accepts_1h': accepts_1h,
            'accepts_24h': accepts_24h,
            # Unique IPs
            'unique_ips_1h': len(ips_1h),
            'unique_ips_24h': len(ips_24h),
            'unique_ips_all': len(ips_all),
            # Top IPs: [(ip, {count, first_seen, last_seen}), ...]
            'top_ips': [(ip, info) for ip, info in top_ips],
            # Auth failures
            'auth_fails_1h': auth_fails_1h,
            'auth_fails_24h': auth_fails_24h,
            'auth_fails_all': auth_fails_all,
            'recent_auth_fails': recent_auth_fails,
            # RPC methods
            'top_methods': top_methods,
            'total_calls_1h': total_calls_1h,
            # Rate
            'conn_rate_per_min': conn_rate_per_min,
            # Timing
            'last_conn_ts': last_conn_ts,
            # Security
            'alerts': list(self._alerts),
            # Has any data been found
            'has_data': has_data,
        }
