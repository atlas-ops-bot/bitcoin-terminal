"""
Main TUI Application
Bitcoin Node Monitor — BBS-inspired dark terminal aesthetic
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from bitcoin_terminal.config import Config
from bitcoin_terminal.rpc import BitcoinRPC
from bitcoin_terminal.log_view import LogScreen
from bitcoin_terminal.ansi_utils import (
    jformat, format_bytes, format_uptime,
)
from bitcoin_terminal.data import (
    fetch_price, fetch_difficulty_adjustment, fetch_hashrate,
    fetch_recommended_fees, fetch_system_metrics,
    SyncTracker, format_hashrate, format_eta,
)

# ── Color palette ──────────────────────────────────────────────────────
BTC_ORANGE = "#F7931A"
NEON_GREEN = "#39FF14"
SOFT_GREEN = "#00E676"
SOFT_RED = "#FF5252"
SOFT_YELLOW = "#FFD740"
CYAN = "#00BCD4"
PURPLE = "#B388FF"
DIM_BORDER = "#444444"

# Halving constants
HALVING_INTERVAL = 210_000


def _make_bar(pct: float, width: int = 20, fill_color: str = BTC_ORANGE,
              empty_color: str = DIM_BORDER) -> Text:
    """Render a Unicode progress bar."""
    filled = int(pct / 100 * width)
    filled = max(0, min(filled, width))
    t = Text()
    t.append("\u2588" * filled, style=fill_color)
    t.append("\u2591" * (width - filled), style=empty_color)
    t.append(f" {pct:.1f}%", style="bold white")
    return t


def _fetch_all_data(rpc: BitcoinRPC) -> Dict[str, Any]:
    """Fetch all node data in one batch (runs in worker thread)."""
    data: Dict[str, Any] = {}
    try:
        data['blockchain'] = rpc.getblockchaininfo()
    except (ConnectionError, Exception) as e:
        data['error'] = str(e)
        data['price'] = fetch_price()
        data['difficulty_adj'] = fetch_difficulty_adjustment()
        data['hashrate'] = fetch_hashrate()
        data['fees'] = fetch_recommended_fees()
        data['system'] = fetch_system_metrics()
        return data

    try:
        data['network'] = rpc.getnetworkinfo()
    except (ConnectionError, Exception):
        data['network'] = {}
    try:
        data['mempool'] = rpc.getmempoolinfo()
    except (ConnectionError, Exception):
        data['mempool'] = {}
    try:
        data['peers'] = rpc.getpeerinfo()
    except (ConnectionError, Exception):
        data['peers'] = []
    try:
        data['uptime'] = rpc.uptime()
    except (ConnectionError, Exception):
        data['uptime'] = 0

    # External APIs (non-critical)
    data['price'] = fetch_price()
    data['difficulty_adj'] = fetch_difficulty_adjustment()
    data['hashrate'] = fetch_hashrate()
    data['fees'] = fetch_recommended_fees()
    data['system'] = fetch_system_metrics()

    return data


def _format_time_ago(secs: int) -> str:
    """Format seconds to human-readable relative time."""
    if secs < 60:
        return f"{secs}s ago"
    elif secs < 3600:
        return f"{secs // 60}m {secs % 60}s ago"
    elif secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    else:
        days = secs // 86400
        hours = (secs % 86400) // 3600
        return f"{days}d {hours}h ago"


def _halving_info(current_height: int) -> Dict[str, Any]:
    """Compute next halving info from block height.

    Uses the HIGHER of synced blocks or network headers to always show
    the correct upcoming halving relative to the actual chain tip.
    """
    next_halving = ((current_height // HALVING_INTERVAL) + 1) * HALVING_INTERVAL
    blocks_remaining = next_halving - current_height
    halving_number = next_halving // HALVING_INTERVAL
    return {
        'next_height': next_halving,
        'blocks_remaining': blocks_remaining,
        'halving_number': halving_number,
    }


# ── Widgets ────────────────────────────────────────────────────────────

class BitcoinHeader(Static):
    """Branded header — single line, auto-width"""

    def on_mount(self) -> None:
        t = Text(justify="center")
        t.append(" \u20bf ", style=f"bold {BTC_ORANGE} on #1a1a1a")
        t.append(" B I T C O I N   N O D E   M O N I T O R ", style=f"bold white on #1a1a1a")
        t.append(" \u20bf ", style=f"bold {BTC_ORANGE} on #1a1a1a")
        self.update(t)


class StatusBar(Static):
    """Live status bar"""

    status = reactive("offline")
    blocks = reactive(0)
    peers = reactive(0)
    chain = reactive("main")
    sync_pct = reactive(0.0)
    btc_price = reactive(0.0)

    def render(self) -> Text:
        line = Text()

        if self.status == "synced":
            line.append(" \u25cf ", style=f"bold {NEON_GREEN}")
            line.append("SYNCED", style=f"bold {NEON_GREEN}")
        elif self.status == "syncing":
            line.append(" \u25d0 ", style=f"bold {SOFT_YELLOW}")
            line.append("SYNCING", style=f"bold {SOFT_YELLOW}")
            if self.sync_pct > 0:
                line.append(f" {self.sync_pct:.2f}%", style=SOFT_YELLOW)
        else:
            line.append(" \u25cb ", style="dim")
            line.append("OFFLINE", style="dim red")

        line.append("  \u2502  ", style=DIM_BORDER)
        chain_colors = {'main': NEON_GREEN, 'test': SOFT_YELLOW,
                        'signet': CYAN, 'regtest': PURPLE}
        line.append(self.chain.upper(),
                    style=f"bold {chain_colors.get(self.chain, 'white')}")

        line.append("  \u2502  ", style=DIM_BORDER)
        line.append("\u29eb ", style=BTC_ORANGE)
        line.append(jformat(self.blocks, 0), style="bold white")

        line.append("  \u2502  ", style=DIM_BORDER)
        line.append("\u21c4 ", style=CYAN)
        line.append(str(self.peers), style="bold white")

        if self.btc_price > 0:
            line.append("  \u2502  ", style=DIM_BORDER)
            line.append("$", style=NEON_GREEN)
            line.append(f"{self.btc_price:,.0f}", style=f"bold {NEON_GREEN}")

        line.append("  \u2502  ", style=DIM_BORDER)
        line.append(datetime.now().strftime("%H:%M:%S"), style="dim")

        return line


class NodeCard(Static):
    """Node health, sync progress, ETA"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.sync_info: Dict[str, Any] = {}

    def update_data(self, blockchain: Dict, network: Dict, uptime: int,
                    sync_info: Dict = None):
        self.data = {
            'blocks': blockchain.get('blocks', 0),
            'headers': blockchain.get('headers', 0),
            'chain': blockchain.get('chain', 'unknown'),
            'sync_pct': blockchain.get('verificationprogress', 0.0) * 100,
            'ibd': blockchain.get('initialblockdownload', False),
            'size_gb': blockchain.get('size_on_disk', 0) / (1024**3),
            'pruned': blockchain.get('pruned', False),
            'version': network.get('version', 0),
            'subversion': network.get('subversion', ''),
            'uptime': uptime,
        }
        self.sync_info = sync_info or {}
        self.refresh()

    def show_error(self, msg: str):
        self.data = {'error': msg}
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Connecting to node...", style="dim italic"),
                         title=f"[bold {BTC_ORANGE}]\u29eb NODE[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        if 'error' in self.data:
            content = Text()
            content.append("  CONNECTION FAILED\n\n", style=f"bold {SOFT_RED}")
            content.append(f"  {self.data['error']}", style="dim")
            return Panel(content, title=f"[bold {SOFT_RED}]\u29eb NODE[/]",
                         border_style=SOFT_RED, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        blocks = self.data.get('blocks', 0)
        headers = self.data.get('headers', 0)
        sync_pct = self.data.get('sync_pct', 0)

        if sync_pct >= 99.99:
            st = Text()
            st.append("\u25cf SYNCED", style=f"bold {NEON_GREEN}")
            t.add_row("Status", st)
        else:
            st = Text()
            st.append("\u25d0 SYNCING", style=f"bold {SOFT_YELLOW}")
            t.add_row("Status", st)
            t.add_row("Progress", _make_bar(sync_pct, width=18))

            eta_secs = self.sync_info.get('eta_seconds', 0)
            bps = self.sync_info.get('blocks_per_sec', 0)
            if eta_secs > 0:
                eta_text = Text()
                eta_text.append(format_eta(eta_secs), style="bold white")
                if bps > 0:
                    eta_text.append(f"  ({bps:.0f} blk/s)", style="dim")
                t.add_row("ETA", eta_text)

        ht = Text()
        ht.append(f"{blocks:,}", style="bold white")
        ht.append(f" / {headers:,}", style="dim")
        t.add_row("Height", ht)

        ver = self.data.get('version', 0)
        if ver:
            t.add_row("Version",
                       f"{ver // 10000}.{(ver // 100) % 100}.{ver % 100}")

        t.add_row("Uptime", format_uptime(self.data.get('uptime', 0)))

        sz = self.data.get('size_gb', 0)
        st = Text()
        st.append(f"{sz:.1f} GB", style="white")
        if self.data.get('pruned'):
            st.append(" PRUNED", style=f"bold {SOFT_YELLOW}")
        t.add_row("Storage", st)

        border = NEON_GREEN if sync_pct >= 99.99 else BTC_ORANGE
        return Panel(t, title=f"[bold {BTC_ORANGE}]\u29eb NODE[/]",
                     border_style=border, box=box.ROUNDED)


class NetworkCard(Static):
    """Network connections"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}

    def update_data(self, network: Dict, peers: list):
        ipv4 = ipv6 = tor = i2p = 0
        for p in peers:
            addr = p.get('addr', '')
            nt = p.get('network', '')
            if nt == 'onion' or '.onion' in addr:
                tor += 1
            elif nt == 'i2p' or '.b32.i2p' in addr:
                i2p += 1
            elif addr.startswith('[') or addr.count(':') > 1:
                ipv6 += 1
            else:
                ipv4 += 1

        self.data = {
            'connections': network.get('connections', 0),
            'connections_in': network.get('connections_in', 0),
            'connections_out': network.get('connections_out', 0),
            'ipv4': ipv4, 'ipv6': ipv6, 'tor': tor, 'i2p': i2p,
            'rx': sum(p.get('bytesrecv', 0) for p in peers),
            'tx': sum(p.get('bytessent', 0) for p in peers),
        }
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Waiting for peers...", style="dim italic"),
                         title=f"[bold {CYAN}]\u21c4 NETWORK[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        total = self.data['connections']
        inn = self.data['connections_in']
        out = self.data['connections_out']
        pt = Text()
        pt.append(str(total), style="bold white")
        pt.append(f"  \u2193{inn}", style=SOFT_GREEN)
        pt.append(f"  \u2191{out}", style=CYAN)
        t.add_row("Peers", pt)

        parts = []
        for label, key, color in [("IPv4", 'ipv4', "white"),
                                   ("IPv6", 'ipv6', "white"),
                                   ("Tor", 'tor', PURPLE),
                                   ("I2P", 'i2p', "#4FC3F7")]:
            v = self.data.get(key, 0)
            if v:
                parts.append((f"{label}:{v}", color))
        if parts:
            tt = Text()
            for i, (txt, col) in enumerate(parts):
                if i:
                    tt.append(" ", style="default")
                tt.append(f" {txt} ", style=f"{col} on {DIM_BORDER}")
            t.add_row("Types", tt)

        tr = Text()
        tr.append(f"\u2193{format_bytes(self.data['rx'])}", style=SOFT_GREEN)
        tr.append(f"  \u2191{format_bytes(self.data['tx'])}", style=CYAN)
        t.add_row("Traffic", tr)

        return Panel(t, title=f"[bold {CYAN}]\u21c4 NETWORK[/]",
                     border_style=CYAN, box=box.ROUNDED)


class PriceCard(Static):
    """Bitcoin price + fees"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.fees: Dict[str, Any] = {}

    def update_data(self, price: Dict, fees: Dict = None):
        self.data = price
        self.fees = fees or {}
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Loading price...", style="dim italic"),
                         title=f"[bold {NEON_GREEN}]$ MARKET[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        usd = self.data.get('usd', 0)
        if usd:
            pt = Text()
            pt.append(f"${usd:,.0f}", style=f"bold {NEON_GREEN}")
            change = self.data.get('usd_24h_change', 0)
            if change:
                color = NEON_GREEN if change >= 0 else SOFT_RED
                arrow = "\u25b2" if change >= 0 else "\u25bc"
                pt.append(f"  {arrow}{abs(change):.1f}%",
                          style=f"bold {color}")
            t.add_row("BTC/USD", pt)

            sats = int(100_000_000 / usd) if usd else 0
            t.add_row("Sats/$", Text(f"{sats:,}", style="bold white"))

            # Moscow time
            moscow_mins = sats % 100
            moscow_hrs = sats // 100
            t.add_row("Moscow \u23f0",
                       Text(f"{moscow_hrs}:{moscow_mins:02d}",
                            style=f"bold {BTC_ORANGE}"))

        # Fee estimates
        if self.fees:
            fastest = self.fees.get('fastest', 0)
            hour = self.fees.get('hour', 0)
            economy = self.fees.get('economy', 0)
            if fastest:
                ft = Text()
                ft.append(f"\u26a1{fastest}", style=f"bold {SOFT_RED}")
                ft.append(f"  \u25d4{hour}", style=SOFT_YELLOW)
                ft.append(f"  \u25f7{economy}", style=SOFT_GREEN)
                ft.append(" sat/vB", style="dim")
                t.add_row("Fees", ft)

        src = self.data.get('source', '')
        return Panel(t, title=f"[bold {NEON_GREEN}]$ MARKET[/]",
                     subtitle=f"[dim]{src}[/]" if src else None,
                     border_style=NEON_GREEN, box=box.ROUNDED)


class MempoolCard(Static):
    """Mempool statistics"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.is_ibd: bool = False

    def update_data(self, mempool: Dict, is_ibd: bool = False):
        self.data = {
            'size': mempool.get('size', 0),
            'bytes': mempool.get('bytes', 0),
            'usage': mempool.get('usage', 0),
            'maxmempool': mempool.get('maxmempool', 0),
            'mempoolminfee': mempool.get('mempoolminfee', 0),
        }
        self.is_ibd = is_ibd
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Waiting for mempool...", style="dim italic"),
                         title=f"[bold {SOFT_YELLOW}]\u23f1 MEMPOOL[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        tx = self.data['size']

        if self.is_ibd and tx == 0:
            notice = Text()
            notice.append("Node syncing\u2026", style=f"bold {SOFT_YELLOW}")
            t.add_row("", notice)
            t.add_row("", Text("Mempool data available\n"
                               "after initial sync",
                               style="dim italic"))
        else:
            tt = Text()
            tt.append(jformat(tx, 0), style="bold white")
            tt.append(" txns", style="dim")
            t.add_row("Pending", tt)

            usage = self.data['usage']
            maxmem = self.data.get('maxmempool', 0)
            t.add_row("Memory", format_bytes(usage))
            if maxmem > 0:
                pct = usage / maxmem * 100
                t.add_row("",
                           _make_bar(pct, width=18, fill_color=SOFT_YELLOW))

            t.add_row("vSize", format_bytes(self.data['bytes']))

            mf = self.data['mempoolminfee']
            if mf > 0:
                t.add_row("Min Fee", f"{mf * 100000:.1f} sat/vB")
            else:
                t.add_row("Min Fee", Text("0", style="dim"))

        return Panel(t, title=f"[bold {SOFT_YELLOW}]\u23f1 MEMPOOL[/]",
                     border_style=SOFT_YELLOW, box=box.ROUNDED)


class BlockchainCard(Static):
    """Blockchain + mining info"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.hashrate_data: Dict[str, Any] = {}
        self.diff_adj: Dict[str, Any] = {}

    def update_data(self, blockchain: Dict, hashrate: Dict = None,
                    diff_adj: Dict = None):
        self.data = {
            'difficulty': blockchain.get('difficulty', 0),
            'mediantime': blockchain.get('mediantime', 0),
            'bestblockhash': blockchain.get('bestblockhash', ''),
            'warnings': blockchain.get('warnings', ''),
            'ibd': blockchain.get('initialblockdownload', False),
            'blocks': blockchain.get('blocks', 0),
        }
        self.hashrate_data = hashrate or {}
        self.diff_adj = diff_adj or {}
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Waiting for chain data...", style="dim italic"),
                         title=f"[bold {PURPLE}]\u26d3 BLOCKCHAIN[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        # Difficulty
        diff = self.data['difficulty']
        if diff > 1e12:
            ds = f"{diff / 1e12:.2f} T"
        elif diff > 1e9:
            ds = f"{diff / 1e9:.2f} B"
        elif diff > 1e6:
            ds = f"{diff / 1e6:.2f} M"
        else:
            ds = f"{diff:,.0f}"
        t.add_row("Difficulty", Text(ds, style="bold white"))

        # Hashrate
        hr = self.hashrate_data.get('hashrate', 0)
        if hr:
            t.add_row("Hashrate",
                       Text(format_hashrate(hr), style="bold white"))

        # Difficulty adjustment
        if self.diff_adj:
            change = self.diff_adj.get('change', 0)
            remaining = self.diff_adj.get('remaining_blocks', 0)
            progress = self.diff_adj.get('progress', 0)

            if change:
                color = NEON_GREEN if change >= 0 else SOFT_RED
                ct = Text()
                ct.append(f"{change:+.2f}%", style=f"bold {color}")
                if remaining:
                    ct.append(f"  ({remaining:,} blk)", style="dim")
                t.add_row("Next Adj", ct)

            retarget_ts = self.diff_adj.get('estimated_retarget', 0)
            if retarget_ts:
                try:
                    retarget_date = datetime.fromtimestamp(
                        retarget_ts / 1000)
                    delta = retarget_date - datetime.now()
                    if delta.total_seconds() > 0:
                        days = delta.days
                        hours = delta.seconds // 3600
                        dt = Text()
                        dt.append(retarget_date.strftime("%b %d"),
                                  style="bold white")
                        dt.append(f"  (in {days}d {hours}h)", style="dim")
                        t.add_row("Retarget", dt)
                except (OSError, ValueError, OverflowError):
                    pass

            if progress:
                t.add_row("Epoch",
                           _make_bar(progress, width=15, fill_color=PURPLE))

            prev = self.diff_adj.get('previous_retarget', 0)
            if prev:
                color = NEON_GREEN if prev >= 0 else SOFT_RED
                t.add_row("Last Adj",
                           Text(f"{prev:+.2f}%", style=color))

        # Last block time
        mt = self.data.get('mediantime', 0)
        if mt > 0:
            block_time = datetime.fromtimestamp(mt)
            secs = int((datetime.now() - block_time).total_seconds())
            is_ibd = self.data.get('ibd', False)

            if is_ibd or secs > 86400:
                t.add_row("Synced To",
                           Text(block_time.strftime("%Y-%m-%d %H:%M"),
                                style=SOFT_YELLOW))
            else:
                t.add_row("Last Block", _format_time_ago(secs))

        # Best hash
        bh = self.data.get('bestblockhash', '')
        if bh:
            ht = Text()
            ht.append(bh[:8], style=BTC_ORANGE)
            ht.append("\u2026", style="dim")
            ht.append(bh[-6:], style=BTC_ORANGE)
            t.add_row("Best", ht)

        w = self.data.get('warnings', '')
        if w:
            t.add_row("Warning", Text(w, style=f"bold {SOFT_RED}"))

        return Panel(t, title=f"[bold {PURPLE}]\u26d3 BLOCKCHAIN[/]",
                     border_style=PURPLE, box=box.ROUNDED)


class HalvingCard(Static):
    """Countdown to next halving — uses network height (headers)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}

    def update_data(self, headers: int):
        """Use headers (network tip) not synced blocks for correct halving."""
        self.data = _halving_info(headers)
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Waiting...", style="dim italic"),
                         title=f"[bold {BTC_ORANGE}]\u23f3 HALVING[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        remaining = self.data.get('blocks_remaining', 0)
        target = self.data.get('next_height', 0)
        halving_num = self.data.get('halving_number', 0)

        t.add_row("Halving #",
                   Text(str(halving_num), style="bold white"))
        t.add_row("Block",
                   Text(f"{target:,}", style=f"bold {BTC_ORANGE}"))
        t.add_row("Remaining",
                   Text(f"{remaining:,} blocks", style="bold white"))

        # ETA: ~10 min per block average
        eta_secs = remaining * 600
        days = eta_secs // 86400
        hours = (eta_secs % 86400) // 3600

        if days > 365:
            years = days / 365.25
            et = Text()
            et.append(f"~{years:.1f} years", style="bold white")
            et.append(f"  ({days:,}d)", style="dim")
            t.add_row("ETA", et)
        elif days > 0:
            t.add_row("ETA",
                       Text(f"~{days}d {hours}h", style="bold white"))

        # Progress through current epoch
        blocks_in_epoch = HALVING_INTERVAL - remaining
        pct = blocks_in_epoch / HALVING_INTERVAL * 100
        t.add_row("Progress",
                   _make_bar(pct, width=15, fill_color=BTC_ORANGE))

        return Panel(t, title=f"[bold {BTC_ORANGE}]\u23f3 HALVING[/]",
                     border_style=BTC_ORANGE, box=box.ROUNDED)


class SystemCard(Static):
    """System metrics: CPU, memory, disk"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}

    def update_data(self, metrics: Dict):
        self.data = metrics
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Loading system info...", style="dim italic"),
                         title=f"[bold {DIM_BORDER}]\u2699 SYSTEM[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        cpu = self.data.get('cpu_percent', 0)
        cpu_color = NEON_GREEN if cpu < 60 else (
            SOFT_YELLOW if cpu < 85 else SOFT_RED)
        t.add_row("CPU", _make_bar(cpu, width=15, fill_color=cpu_color))

        mp = self.data.get('mem_percent', 0)
        mem_used = self.data.get('mem_used', 0)
        mem_total = self.data.get('mem_total', 0)
        mem_color = NEON_GREEN if mp < 70 else (
            SOFT_YELLOW if mp < 90 else SOFT_RED)
        t.add_row("Memory", _make_bar(mp, width=15, fill_color=mem_color))
        mt = Text()
        mt.append(f"{format_bytes(mem_used)}", style="white")
        mt.append(f" / {format_bytes(mem_total)}", style="dim")
        t.add_row("", mt)

        dp = self.data.get('disk_percent', 0)
        disk_used = self.data.get('disk_used', 0)
        disk_total = self.data.get('disk_total', 0)
        disk_color = NEON_GREEN if dp < 75 else (
            SOFT_YELLOW if dp < 90 else SOFT_RED)
        t.add_row("Disk", _make_bar(dp, width=15, fill_color=disk_color))
        dt = Text()
        dt.append(f"{format_bytes(disk_used)}", style="white")
        dt.append(f" / {format_bytes(disk_total)}", style="dim")
        t.add_row("", dt)

        return Panel(t, title=f"[bold {DIM_BORDER}]\u2699 SYSTEM[/]",
                     border_style=DIM_BORDER, box=box.ROUNDED)


class ConfigCard(Static):
    """Compact bitcoin.conf display"""

    def __init__(self, datadir: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datadir = datadir
        self.config_items: list = []
        self.load_config()

    def load_config(self):
        conf_path = self.datadir / 'bitcoin.conf'
        if not conf_path.exists():
            return
        try:
            with open(conf_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('['):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key not in ('rpcpassword',):
                            value = value.split('#')[0].strip()
                        if any(s in key.lower()
                               for s in ['password', 'rpcauth']):
                            if 'user' not in key.lower():
                                value = "\u2022" * 8
                        self.config_items.append((key, value))
                    else:
                        self.config_items.append((line, "enabled"))
        except (OSError, IOError):
            pass

    def render(self) -> Panel:
        if not self.config_items:
            return Panel(Text("  bitcoin.conf not found", style="dim italic"),
                         title=f"[bold {DIM_BORDER}]\u2699 CONFIG[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 2), expand=True)
        t.add_column("S", style=BTC_ORANGE, width=20)
        t.add_column("V", style="white", no_wrap=False)

        important = ['server', 'daemon', 'prune', 'txindex', 'rpcuser',
                     'rpcport', 'maxconnections', 'blocksdir', 'dbcache']
        shown = set()
        for key in important:
            for ck, cv in self.config_items:
                if ck.lower() == key.lower() and ck not in shown:
                    vt = Text()
                    if cv in ('1', 'enabled'):
                        vt.append(cv, style=NEON_GREEN)
                    elif cv in ('0',):
                        vt.append(cv, style="dim")
                    elif '\u2022' in cv:
                        vt.append(cv, style="dim")
                    else:
                        vt.append(cv, style="white")
                    t.add_row(ck, vt)
                    shown.add(ck)
        for ck, cv in self.config_items:
            if ck not in shown:
                vt = Text()
                if cv in ('1', 'enabled'):
                    vt.append(cv, style=NEON_GREEN)
                elif '\u2022' in cv:
                    vt.append(cv, style="dim")
                else:
                    vt.append(cv, style="white")
                t.add_row(ck, vt)

        return Panel(t, title=f"[bold {DIM_BORDER}]\u2699 CONFIG[/]",
                     subtitle=f"[dim]{self.datadir / 'bitcoin.conf'}[/]",
                     border_style=DIM_BORDER, box=box.ROUNDED)


# ── Main App ───────────────────────────────────────────────────────────

class BitcoinTUI(App):
    """Bitcoin Terminal - Full-Featured Node Monitor"""

    CSS = """
    Screen {
        background: #0a0a0a;
    }
    BitcoinHeader {
        height: 1;
        margin: 0 1 0 1;
        content-align: center middle;
    }
    StatusBar {
        height: 1;
        margin: 0 1 0 1;
        background: #111111;
        padding: 0 1;
    }
    .cards-row {
        height: 1fr;
        min-height: 10;
    }
    .card {
        width: 1fr;
        height: 100%;
        margin: 0 1 0 0;
        overflow-y: auto;
    }
    #config-row {
        display: none;
        height: auto;
        max-height: 14;
    }
    #config-row .card {
        height: auto;
    }
    Footer {
        background: #111111;
    }
    """

    BINDINGS = [
        ("q", "quit",          "Quit"),
        ("r", "refresh",       "Refresh"),
        ("c", "toggle_config", "Config"),
        ("l", "view_logs",     "Logs"),
    ]

    def __init__(self, datadir: Optional[str] = None):
        super().__init__()
        self.config = Config()
        self.datadir = Path(datadir) if datadir else self.config.get_datadir()
        self.rpc: Optional[BitcoinRPC] = None
        self._refresh_interval = self.config.get_display_config().get(
            'refresh_interval', 5)
        self._sync_tracker = SyncTracker()
        self._shutting_down = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield BitcoinHeader()
        self.status_bar = StatusBar()
        yield self.status_bar

        # Row 1: Node | Network | Price
        with Horizontal(classes="cards-row"):
            self.node_card = NodeCard(classes="card")
            yield self.node_card
            self.network_card = NetworkCard(classes="card")
            yield self.network_card
            self.price_card = PriceCard(classes="card")
            yield self.price_card

        # Row 2: Mempool | Blockchain | Halving
        with Horizontal(classes="cards-row"):
            self.mempool_card = MempoolCard(classes="card")
            yield self.mempool_card
            self.blockchain_card = BlockchainCard(classes="card")
            yield self.blockchain_card
            self.halving_card = HalvingCard(classes="card")
            yield self.halving_card

        # Row 3: System (full width)
        with Horizontal(classes="cards-row"):
            self.system_card = SystemCard(classes="card")
            yield self.system_card

        # Config (hidden by default, toggle with 'c')
        if self.datadir:
            with Horizontal(id="config-row"):
                self.config_card = ConfigCard(self.datadir, classes="card")
                yield self.config_card

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Bitcoin Terminal"
        self.sub_title = str(self.datadir) if self.datadir else "No datadir"

        if self.datadir and self.datadir.exists():
            env_rpc = self.config.get_rpc_config()
            self.rpc = BitcoinRPC.from_datadir(self.datadir,
                                                env_config=env_rpc)

        self.refresh_data()
        self.set_interval(self._refresh_interval, self.refresh_data)

    def refresh_data(self) -> None:
        if self.rpc and not self._shutting_down:
            self.run_worker(self._fetch_and_update, thread=True,
                            exclusive=True)

    def _fetch_and_update(self) -> None:
        if not self.rpc or self._shutting_down:
            return
        data = _fetch_all_data(self.rpc)
        if not self._shutting_down:
            self.call_from_thread(self._apply_data, data)

    def _apply_data(self, data: Dict[str, Any]) -> None:
        if self._shutting_down:
            return

        blockchain = data.get('blockchain', {})
        network = data.get('network', {})
        mempool = data.get('mempool', {})
        peers = data.get('peers', [])
        uptime = data.get('uptime', 0)
        price = data.get('price', {})
        fees = data.get('fees', {})
        hashrate = data.get('hashrate', {})
        diff_adj = data.get('difficulty_adj', {})
        system = data.get('system', {})

        if 'error' in data:
            self.node_card.show_error(data['error'])
            self.status_bar.status = "offline"
            self.price_card.update_data(price, fees=fees)
            self.system_card.update_data(system)
            if hashrate or diff_adj:
                self.blockchain_card.update_data(
                    {'difficulty': 0, 'mediantime': 0,
                     'bestblockhash': '', 'warnings': ''},
                    hashrate=hashrate, diff_adj=diff_adj)
            return

        is_ibd = blockchain.get('initialblockdownload', False)
        blocks = blockchain.get('blocks', 0)
        headers = blockchain.get('headers', 0)
        sync_info = self._sync_tracker.update(blocks, headers)

        self.node_card.update_data(blockchain, network, uptime,
                                   sync_info=sync_info)
        self.network_card.update_data(network, peers)
        self.mempool_card.update_data(mempool, is_ibd=is_ibd)
        self.blockchain_card.update_data(blockchain, hashrate=hashrate,
                                         diff_adj=diff_adj)
        self.price_card.update_data(price, fees=fees)
        self.system_card.update_data(system)

        # Halving: use headers (network tip) so number is correct
        # even during initial sync
        if headers > 0:
            self.halving_card.update_data(headers)

        # Status bar
        sync_pct = blockchain.get('verificationprogress', 0.0) * 100
        self.status_bar.sync_pct = sync_pct
        self.status_bar.chain = blockchain.get('chain', 'main')
        self.status_bar.status = (
            "synced" if sync_pct >= 99.99 else "syncing")
        self.status_bar.blocks = blocks
        self.status_bar.peers = network.get('connections', 0)
        self.status_bar.btc_price = price.get('usd', 0)

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Refreshed", timeout=1)

    def action_toggle_config(self) -> None:
        try:
            container = self.query_one("#config-row")
            container.display = not container.display
        except Exception:
            pass

    def action_view_logs(self) -> None:
        log_path = self._get_log_path()
        self.push_screen(LogScreen(log_path))

    def _get_log_path(self) -> Optional[Path]:
        """Resolve debug.log, checking chain subdirectories."""
        if not self.datadir:
            return None
        # Main data dir first (mainnet)
        main_log = self.datadir / "debug.log"
        if main_log.exists():
            return main_log
        # Chain subdirectories
        for sub in ("testnet3", "testnet4", "signet", "regtest"):
            p = self.datadir / sub / "debug.log"
            if p.exists():
                return p
        # Return expected path even if it doesn't exist yet
        return main_log

    def action_quit(self) -> None:
        self._shutting_down = True
        self.exit()


if __name__ == "__main__":
    app = BitcoinTUI()
    app.run()
