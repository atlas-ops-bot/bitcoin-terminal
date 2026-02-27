"""
External data fetchers
Bitcoin price, hashrate, difficulty adjustment via public APIs
System metrics via psutil
"""

import json
import urllib.request
import urllib.error
import time
from typing import Dict, Any, Optional

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


def fetch_price() -> Dict[str, Any]:
    """Fetch BTC price from CoinGecko (has 24h change), fallback to mempool.space."""
    # Try CoinGecko first (includes 24h change)
    data = _fetch_json(
        'https://api.coingecko.com/api/v3/simple/price'
        '?ids=bitcoin&vs_currencies=usd'
        '&include_24hr_change=true'
    )
    if data and 'bitcoin' in data:
        btc = data['bitcoin']
        return {
            'usd': btc.get('usd', 0),
            'usd_24h_change': btc.get('usd_24h_change', 0),
            'source': 'coingecko',
        }

    # Fallback: mempool.space (no 24h change available)
    data = _fetch_json('https://mempool.space/api/v1/prices')
    if data and 'USD' in data:
        return {
            'usd': data['USD'],
            'source': 'mempool.space',
        }

    return {}


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
        return {
            'hashrate': data['currentHashrate'],
            'difficulty': data.get('currentDifficulty', 0),
        }
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

def fetch_system_metrics() -> Dict[str, Any]:
    """Get CPU, memory, and disk usage."""
    if not HAS_PSUTIL:
        return {}

    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot = psutil.boot_time()

        return {
            'cpu_percent': cpu_pct,
            'mem_total': mem.total,
            'mem_used': mem.used,
            'mem_percent': mem.percent,
            'disk_total': disk.total,
            'disk_used': disk.used,
            'disk_percent': disk.percent,
            'boot_time': boot,
        }
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
