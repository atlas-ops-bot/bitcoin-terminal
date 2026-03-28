"""
Main TUI Application
Bitcoin Node Monitor — BBS-inspired dark terminal aesthetic
"""

import time
import random

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Center, Grid
from textual.widgets import Header, Footer, Static, Button
from textual.screen import ModalScreen
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
from bitcoin_terminal.config_screen import ConfigScreen
from bitcoin_terminal.display_settings import (
    load_display_settings, DisplaySettingsScreen,
)
import pyfiglet

from bitcoin_terminal.ansi_utils import (
    jformat, format_bytes, format_uptime,
)
from bitcoin_terminal.data import (
    fetch_price, fetch_difficulty_adjustment, fetch_hashrate,
    fetch_recommended_fees, fetch_system_metrics, fetch_network_tip,
    SyncTracker, format_hashrate, format_eta,
    PeerTracker, RPCMonitor,
    block_subsidy, total_mined, MAX_SUPPLY,
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

# Satoshi Nakamoto quotes — sourced from public posts and emails
SATOSHI_QUOTES = [
    {
        "text": "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks.",
        "date": "2009-01-03",
        "source": "Genesis Block",
    },
    {
        "text": "I've been working on a new electronic cash system that's fully "
                "peer-to-peer, with no trusted third party.",
        "date": "2008-10-31",
        "source": "Cryptography Mailing List",
    },
    {
        "text": "The root problem with conventional currency is all the trust "
                "that's required to make it work.",
        "date": "2009-02-11",
        "source": "P2P Foundation",
    },
    {
        "text": "Lost coins only make everyone else's coins worth slightly more. "
                "Think of it as a donation to everyone.",
        "date": "2010-06-21",
        "source": "BitcoinTalk",
    },
    {
        "text": "It might make sense just to get some in case it catches on.",
        "date": "2009-01-17",
        "source": "Cryptography Mailing List",
    },
    {
        "text": "I'm sure that in 20 years there will either be very large "
                "transaction volume or no volume.",
        "date": "2010-02-14",
        "source": "BitcoinTalk",
    },
    {
        "text": "The nature of Bitcoin is such that once version 0.1 was released, "
                "the core design was set in stone for the rest of its lifetime.",
        "date": "2010-06-17",
        "source": "BitcoinTalk",
    },
    {
        "text": "If you don't believe me or don't understand, I don't have time "
                "to try to convince you, sorry.",
        "date": "2010-07-29",
        "source": "BitcoinTalk",
    },
    {
        "text": "Writing a description for this thing for general audiences is "
                "bloody hard. There's nothing to relate it to.",
        "date": "2009-01-15",
        "source": "Email to Dustin Trammell",
    },
    {
        "text": "We can win a major battle in the arms race and gain a new "
                "territory of freedom for several years.",
        "date": "2008-11-07",
        "source": "Cryptography Mailing List",
    },
    {
        "text": "The proof-of-work chain is a solution to the Byzantine "
                "Generals' Problem.",
        "date": "2008-11-13",
        "source": "Cryptography Mailing List",
    },
    {
        "text": "Being open source means anyone can independently review the code.",
        "date": "2009-12-10",
        "source": "BitcoinTalk",
    },
    {
        "text": "SHA-256 is very strong. It can last several decades unless "
                "there's some massive breakthrough attack.",
        "date": "2010-08-09",
        "source": "BitcoinTalk",
    },
    {
        "text": "For greater privacy, it's best to use bitcoin addresses only once.",
        "date": "2008-10-31",
        "source": "Bitcoin Whitepaper",
    },
    {
        "text": "With e-currency based on cryptographic proof, without the need "
                "to trust a third party middleman, money can be secure.",
        "date": "2009-02-11",
        "source": "P2P Foundation",
    },
]


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


def _fetch_all_data(rpc: BitcoinRPC, datadir: str = None) -> Dict[str, Any]:
    """Fetch all node data in one batch (runs in worker thread)."""
    data: Dict[str, Any] = {}
    try:
        data['blockchain'] = rpc.getblockchaininfo()
    except Exception as e:
        data['error'] = str(e)
        data['price'] = fetch_price()
        data['difficulty_adj'] = fetch_difficulty_adjustment()
        data['hashrate'] = fetch_hashrate()
        data['fees'] = fetch_recommended_fees()
        data['system'] = fetch_system_metrics(datadir=datadir)
        return data

    try:
        data['network'] = rpc.getnetworkinfo()
    except Exception:
        data['network'] = {}
    try:
        data['mempool'] = rpc.getmempoolinfo()
    except Exception:
        data['mempool'] = {}
    try:
        data['peers'] = rpc.getpeerinfo()
    except Exception:
        data['peers'] = []
    try:
        data['uptime'] = rpc.uptime()
    except Exception:
        data['uptime'] = 0

    # Fetch actual latest block time (not mediantime)
    try:
        best_hash = data['blockchain'].get('bestblockhash', '')
        if best_hash:
            block = rpc.getblock(best_hash)
            data['last_block_time'] = block.get('time', 0)
    except Exception:
        pass

    # Block timing stats (epoch avg + 24h avg)
    try:
        height = data['blockchain'].get('blocks', 0)
        tip_time = data.get('last_block_time', 0)
        if height > 2016 and tip_time > 0:
            # Epoch average: time from epoch start block to tip
            epoch_start_h = height - (height % 2016)
            blocks_in_epoch = height - epoch_start_h
            if blocks_in_epoch > 0:
                epoch_hash = rpc.getblockhash(epoch_start_h)
                epoch_block = rpc.getblock(epoch_hash)
                epoch_start_ts = epoch_block.get('time', 0)
                if epoch_start_ts > 0:
                    epoch_elapsed = tip_time - epoch_start_ts
                    epoch_avg = epoch_elapsed / blocks_in_epoch
                else:
                    epoch_avg = None
            else:
                epoch_avg = None

            # 24h average: sample block ~144 blocks ago
            sample_depth = min(144, height - 1)
            sample_h = height - sample_depth
            sample_hash = rpc.getblockhash(sample_h)
            sample_block = rpc.getblock(sample_hash)
            sample_ts = sample_block.get('time', 0)
            if sample_ts > 0 and tip_time > sample_ts:
                avg_24h = (tip_time - sample_ts) / sample_depth
            else:
                avg_24h = None

            data['block_time_stats'] = {
                'epoch_avg': epoch_avg,
                'avg_24h': avg_24h,
                'blocks_in_epoch': blocks_in_epoch,
            }

            # Average fee as % of block reward (sample 6 blocks over last 144)
            try:
                sample_heights = []
                step = max(1, sample_depth // 5)
                for i in range(6):
                    sh = height - i * step
                    if sh > 0:
                        sample_heights.append(sh)
                fee_pcts = []
                for sh in sample_heights:
                    bs = rpc.getblockstats(
                        sh, ['totalfee', 'subsidy'])
                    tfee = bs.get('totalfee', 0)   # satoshis
                    sub = bs.get('subsidy', 0)      # satoshis
                    if sub > 0:
                        fee_pcts.append(tfee / sub * 100)
                if fee_pcts:
                    data['block_time_stats']['avg_fee_pct'] = (
                        sum(fee_pcts) / len(fee_pcts))
            except Exception:
                pass
    except Exception:
        pass

    # External APIs (non-critical)
    data['price'] = fetch_price()
    data['difficulty_adj'] = fetch_difficulty_adjustment()
    data['hashrate'] = fetch_hashrate()
    data['fees'] = fetch_recommended_fees()
    data['system'] = fetch_system_metrics(datadir=datadir)

    # Network tip from mempool.space — fixes "headers == blocks" on
    # startup before Bitcoin Core's own header sync finishes.
    blocks = data['blockchain'].get('blocks', 0)
    headers = data['blockchain'].get('headers', 0)
    if headers <= blocks and data['blockchain'].get(
            'verificationprogress', 1.0) < 0.9999:
        net_tip = fetch_network_tip()
        if net_tip > headers:
            data['blockchain']['headers'] = net_tip

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


def _format_behind(secs: int) -> str:
    """Format seconds-behind-tip into a human-readable string."""
    if secs < 3600:
        return f"{secs // 60}m behind"
    elif secs < 86400:
        h = secs // 3600
        m = (secs % 3600) // 60
        return f"{h}h {m}m behind"
    elif secs < 86400 * 7:
        d = secs // 86400
        h = (secs % 86400) // 3600
        return f"{d}d {h}h behind"
    elif secs < 86400 * 30:
        w = secs // (86400 * 7)
        d = (secs % (86400 * 7)) // 86400
        return f"{w}w {d}d behind"
    elif secs < 86400 * 365:
        mo = secs // (86400 * 30)
        d = (secs % (86400 * 30)) // 86400
        return f"{mo}mo {d}d behind"
    else:
        y = secs // (86400 * 365)
        mo = (secs % (86400 * 365)) // (86400 * 30)
        return f"{y}y {mo}mo behind"


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
    """Live status bar with configurable item visibility."""

    status = reactive("offline")
    blocks = reactive(0)
    peers = reactive(0)
    chain = reactive("main")
    sync_pct = reactive(0.0)
    btc_price = reactive(0.0)
    epoch_avg = reactive(0.0)
    hashprice = reactive(0.0)
    fee_pct = reactive(0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visible_items: Dict[str, bool] = {
            'status': True, 'chain': True, 'blocks': True,
            'peers': True, 'price': True, 'hashprice': True,
            'epoch_avg': True, 'fee_pct': True, 'time': True,
        }

    def render(self) -> Text:
        line = Text()
        vis = self.visible_items
        sep = ("  \u2502  ", DIM_BORDER)

        if vis.get('status', True):
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

        if vis.get('chain', True):
            line.append(*sep)
            chain_colors = {'main': NEON_GREEN, 'test': SOFT_YELLOW,
                            'signet': CYAN, 'regtest': PURPLE}
            line.append(self.chain.upper(),
                        style=f"bold {chain_colors.get(self.chain, 'white')}")

        if vis.get('blocks', True):
            line.append(*sep)
            line.append("\u29eb ", style=BTC_ORANGE)
            line.append(jformat(self.blocks, 0), style="bold white")

        if vis.get('peers', True):
            line.append(*sep)
            line.append("\u21c4 ", style=CYAN)
            line.append(str(self.peers), style="bold white")

        if vis.get('price', True) and self.btc_price > 0:
            line.append(*sep)
            line.append("$", style=NEON_GREEN)
            line.append(f"{self.btc_price:,.0f}", style=f"bold {NEON_GREEN}")

        if vis.get('hashprice', True) and self.hashprice > 0:
            line.append(*sep)
            line.append(f"${self.hashprice:,.2f}", style=f"bold {NEON_GREEN}")
            line.append("/PH", style="dim")

        if vis.get('epoch_avg', True) and self.epoch_avg > 0:
            line.append(*sep)
            mins = int(self.epoch_avg // 60)
            secs = int(self.epoch_avg % 60)
            if self.epoch_avg < 540:
                color = NEON_GREEN
            elif self.epoch_avg <= 660:
                color = CYAN
            else:
                color = SOFT_YELLOW
            line.append("\u23f1 ", style="dim")
            line.append(f"{mins}m{secs:02d}s", style=f"bold {color}")

        if vis.get('fee_pct', True) and self.fee_pct > 0:
            line.append(*sep)
            fc = NEON_GREEN if self.fee_pct < 10 else (
                SOFT_YELLOW if self.fee_pct < 50 else BTC_ORANGE)
            line.append("Fee ", style="dim")
            line.append(f"{self.fee_pct:.1f}%", style=f"bold {fc}")

        if vis.get('time', True):
            line.append(*sep)
            line.append(datetime.now().strftime("%H:%M:%S"), style="dim")

        return line


class NodeCard(Static):
    """Node health, sync progress, ETA"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.sync_info: Dict[str, Any] = {}

    def update_data(self, blockchain: Dict, network: Dict, uptime: int,
                    sync_info: Dict = None, last_block_time: int = 0):
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
            'last_block_time': last_block_time,
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

        catching_up = (headers > 0 and (headers - blocks) > 3)
        fully_synced = sync_pct >= 99.99 and not catching_up and not self.data.get('ibd', False)

        if fully_synced:
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

            # How far behind the network tip
            lbt = self.data.get('last_block_time', 0)
            if lbt > 0:
                behind_secs = int(time.time() - lbt)
                if behind_secs > 60:
                    t.add_row("Behind", Text(
                        _format_behind(behind_secs),
                        style=f"bold {SOFT_YELLOW}"))

        ht = Text()
        ht.append(f"{blocks:,}", style="bold white")
        ht.append(f" / {headers:,}", style="dim")
        t.add_row("Height", ht)

        ver = self.data.get('version', 0)
        subver = self.data.get('subversion', '')
        if subver:
            # e.g. "/Satoshi:27.0.0/" → "Satoshi 27.0.0"
            display_ver = subver.strip('/').replace(':', ' ')
            t.add_row("Version", Text(display_ver, style="white"))
        elif ver:
            t.add_row("Version",
                       f"{ver // 10000}.{(ver // 100) % 100}.{ver % 100}")

        t.add_row("Uptime", format_uptime(self.data.get('uptime', 0)))

        sz = self.data.get('size_gb', 0)
        st = Text()
        st.append(f"{sz:.1f} GB", style="white")
        if self.data.get('pruned'):
            st.append(" PRUNED", style=f"bold {SOFT_YELLOW}")
        t.add_row("Storage", st)

        border = NEON_GREEN if fully_synced else BTC_ORANGE
        return Panel(t, title=f"[bold {BTC_ORANGE}]\u29eb NODE[/]",
                     border_style=border, box=box.ROUNDED)


class NetworkCard(Static):
    """P2P network peer connections with historical tracking"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.conn_stats: Dict[str, Any] = {}

    def update_data(self, network: Dict, peers: list,
                    conn_stats: Dict = None):
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
        self.conn_stats = conn_stats or {}
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Waiting for peers...", style="dim italic"),
                         title=f"[bold {CYAN}]\u21c4 P2P PEERS[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        # ── Live connections ──
        total = self.data['connections']
        inn = self.data['connections_in']
        out = self.data['connections_out']
        pt = Text()
        pt.append(str(total), style="bold white")
        pt.append(f"  \u2193{inn}", style=SOFT_GREEN)
        pt.append(f"  \u2191{out}", style=CYAN)
        t.add_row("Peers", pt)

        # Network types
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

        # Bandwidth total + rate
        tr = Text()
        tr.append(f"\u2193{format_bytes(self.data['rx'])}", style=SOFT_GREEN)
        tr.append(f"  \u2191{format_bytes(self.data['tx'])}", style=CYAN)
        t.add_row("Traffic", tr)

        if self.conn_stats:
            cs = self.conn_stats

            # Bandwidth rate
            rx_rate = cs.get('rx_rate', 0)
            tx_rate = cs.get('tx_rate', 0)
            if rx_rate > 0 or tx_rate > 0:
                rt = Text()
                rt.append(f"\u2193{format_bytes(rx_rate)}/s", style=SOFT_GREEN)
                rt.append(f"  \u2191{format_bytes(tx_rate)}/s", style=CYAN)
                t.add_row("Rate", rt)

            # Unique peers seen
            u1h = cs.get('unique_1h', 0)
            u24h = cs.get('unique_24h', 0)
            u_all = cs.get('unique_all', 0)
            ut = Text()
            ut.append(f"{u1h}", style="bold white")
            ut.append(" 1h", style="dim")
            ut.append(f"  {u24h}", style="bold white")
            ut.append(" 24h", style="dim")
            ut.append(f"  {u_all}", style=f"bold {BTC_ORANGE}")
            ut.append(" all", style="dim")
            t.add_row("Seen", ut)

            # Peak / average connections
            peak = cs.get('peak_24h', 0)
            avg = cs.get('avg_24h', 0)
            if peak > 0:
                st = Text()
                st.append(f"\u2191{peak}", style=f"bold {NEON_GREEN}")
                st.append(" peak", style="dim")
                st.append(f"  \u00f8{avg:.0f}", style="bold white")
                st.append(" avg", style="dim")
                t.add_row("Range", st)

            # Churn: connections / disconnections last hour
            conn_1h = cs.get('connects_1h', 0)
            disc_1h = cs.get('disconnects_1h', 0)
            if conn_1h > 0 or disc_1h > 0:
                ct = Text()
                ct.append(f"+{conn_1h}", style=SOFT_GREEN)
                ct.append(f"  -{disc_1h}", style=SOFT_RED)
                ct.append(" /1h", style="dim")
                t.add_row("Churn", ct)

            # Average / longest connection duration
            avg_dur = cs.get('avg_duration', 0)
            max_dur = cs.get('max_duration', 0)
            if avg_dur > 0:
                dt = Text()
                dt.append(format_uptime(int(avg_dur)), style="bold white")
                dt.append(" avg", style="dim")
                if max_dur > 0:
                    dt.append(f"  {format_uptime(int(max_dur))}", style="dim")
                    dt.append(" max", style="dim")
                t.add_row("Duration", dt)

            # Security alerts
            alerts = cs.get('alerts', [])
            for alert in alerts[:2]:
                level = alert.get('level', 'info')
                msg = alert.get('msg', '')
                color = SOFT_RED if level == 'warning' else SOFT_YELLOW
                at = Text()
                at.append("\u26a0 ", style=f"bold {color}")
                at.append(msg, style=color)
                t.add_row("Alert", at)

        return Panel(t, title=f"[bold {CYAN}]\u21c4 P2P PEERS[/]",
                     border_style=CYAN, box=box.ROUNDED)


class PriceCard(Static):
    """Large figlet BTC price — warden-inspired hero display"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}
        self.fees: Dict[str, Any] = {}
        self.block_time_stats: Dict[str, Any] = {}
        self.figlet_font: str = 'small'

    def update_data(self, price: Dict, fees: Dict = None,
                    block_time_stats: Dict[str, Any] = None):
        self.data = price
        self.fees = fees or {}
        if block_time_stats is not None:
            self.block_time_stats = block_time_stats
        self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(Text("  Loading price\u2026", style="dim italic"),
                         title=f"[bold {NEON_GREEN}]\u20bf BTC PRICE[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        usd = self.data.get('usd', 0)
        if not usd:
            return Panel(Text("  Price unavailable", style="dim italic"),
                         title=f"[bold {NEON_GREEN}]\u20bf BTC PRICE[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        # Available width inside the panel (borders + padding ≈ 4)
        card_w = self.size.width - 4 if self.size.width > 0 else 80
        use_figlet = card_w >= 30

        # Render price display
        if use_figlet:
            try:
                fig = pyfiglet.Figlet(font=self.figlet_font)
                price_str = f"$ {usd:,.0f}"
                raw = fig.renderText(price_str)
                lines = [ln for ln in raw.split('\n') if ln.strip()]
                max_w = max((len(ln) for ln in lines), default=0)
                # If figlet is wider than card allows, fall back
                if max_w > card_w - 12:
                    use_figlet = False
                else:
                    lines = [ln.ljust(max_w) for ln in lines]
                    large_text = '\n'.join(lines)
            except Exception:
                use_figlet = False

        figlet_block = Text()
        if use_figlet:
            for line in large_text.split('\n'):
                figlet_block.append(line + '\n', style=f"bold {NEON_GREEN}")
        else:
            figlet_block.append(f"\n  $ {usd:,.0f}\n",
                                style=f"bold {NEON_GREEN}")

        # Build right-side info column (stacked vertically)
        info = Text()

        # 24h change
        change = self.data.get('usd_24h_change', 0)
        if change:
            color = NEON_GREEN if change >= 0 else SOFT_RED
            arrow = "\u25b2" if change >= 0 else "\u25bc"
            info.append("24h  ", style="dim")
            info.append(f"{arrow}{abs(change):.1f}%",
                        style=f"bold {color}")
            info.append("\n")

        # Sats per dollar
        sats = int(100_000_000 / usd)
        info.append("Sats ", style="dim")
        info.append(f"{sats:,}", style="bold white")
        info.append("\n")

        # Moscow time
        moscow_mins = sats % 100
        moscow_hrs = sats // 100
        info.append("\u23f0   ", style="dim")
        info.append(f"{moscow_hrs}:{moscow_mins:02d}",
                    style=f"bold {BTC_ORANGE}")
        info.append("\n")

        # Fee estimates
        if self.fees:
            fastest = self.fees.get('fastest', 0)
            hour = self.fees.get('hour', 0)
            economy = self.fees.get('economy', 0)
            if fastest:
                info.append("\u26a1   ", style="dim")
                info.append(f"{fastest}", style=f"bold {SOFT_RED}")
                info.append(f"/{hour}", style=SOFT_YELLOW)
                info.append(f"/{economy}", style=SOFT_GREEN)
                info.append("\n")

        # Hashprice ($/PH/day)
        hp = self.block_time_stats.get('hashprice')
        if hp is not None:
            info.append("\u26cf   ", style="dim")
            info.append(f"${hp:,.2f}", style=f"bold {NEON_GREEN}")
            info.append("/PH/d", style="dim")
            info.append("\n")

        # Source label
        src = self.data.get('source', '')
        if src:
            info.append("source ", style="dim grey62")
            info.append(src, style=NEON_GREEN)
            info.append("\n")

        # Side-by-side layout if enough room, stacked otherwise
        if card_w >= 40:
            layout = Table.grid(padding=(0, 2), expand=True)
            layout.add_column("price", ratio=3)
            layout.add_column("info", ratio=1)
            layout.add_row(figlet_block, info)
        else:
            figlet_block.append("\n")
            figlet_block.append_text(info)
            layout = figlet_block

        return Panel(layout,
                     title=f"[bold {NEON_GREEN}]\u20bf BTC PRICE[/]",
                     border_style=NEON_GREEN, box=box.ROUNDED)


class BlockHeightCard(Static):
    """Large figlet block height with epoch timing stats"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_height: int = 0
        self.last_block_time: int = 0
        self.is_ibd: bool = False
        self.block_time_stats: Dict[str, Any] = {}
        self.diff_adj: Dict[str, Any] = {}
        self.figlet_font: str = 'small'

    def update_data(self, blocks: int, last_block_time: int = 0,
                    is_ibd: bool = False,
                    block_time_stats: Dict[str, Any] = None,
                    diff_adj: Dict[str, Any] = None):
        self.block_height = blocks
        self.last_block_time = last_block_time
        self.is_ibd = is_ibd
        if block_time_stats is not None:
            self.block_time_stats = block_time_stats
        if diff_adj is not None:
            self.diff_adj = diff_adj
        self.refresh()

    def _build_epoch_stats(self) -> Table:
        """Build a compact stats column for epoch/block timing."""
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column("K", style="dim", width=11)
        tbl.add_column("V", style="white")

        bts = self.block_time_stats
        da = self.diff_adj
        height = self.block_height

        # Blocks in current epoch / remaining
        epoch_start = height - (height % 2016)
        blocks_in = height - epoch_start
        blocks_left = 2016 - blocks_in
        epoch_pct = blocks_in / 2016 * 100

        tbl.add_row("Epoch Blks", Text(f"{blocks_in:,} / 2,016", style="bold white"))
        tbl.add_row("Remaining", Text(f"{blocks_left:,}", style="white"))
        tbl.add_row("Progress", _make_bar(epoch_pct, width=12, fill_color=PURPLE))

        # Target: expected blocks at this point vs actual
        # Each epoch should take 2016 * 600s = ~14 days
        if bts.get('epoch_avg'):
            epoch_avg = bts['epoch_avg']
            # Expected elapsed time for blocks_in blocks at 10min target
            expected_elapsed = blocks_in * 600
            actual_elapsed = blocks_in * epoch_avg
            # Blocks ahead/behind: how many more (or fewer) blocks than
            # expected given the actual time elapsed
            expected_blocks = actual_elapsed / 600 if actual_elapsed > 0 else 0
            delta = blocks_in - expected_blocks

            if delta > 0:
                delta_text = Text(f"+{delta:.0f} ahead", style=f"bold {NEON_GREEN}")
            elif delta < 0:
                delta_text = Text(f"{delta:.0f} behind", style=f"bold {SOFT_RED}")
            else:
                delta_text = Text("On target", style=f"bold {NEON_GREEN}")
            tbl.add_row("Schedule", delta_text)

        # Epoch avg block time
        if bts.get('epoch_avg'):
            avg = bts['epoch_avg']
            mins = avg / 60
            if avg < 540:       # < 9 min → fast
                color, label = NEON_GREEN, "Fast"
            elif avg <= 660:    # 9-11 min → normal
                color, label = SOFT_GREEN, "Normal"
            else:               # > 11 min → slow
                color, label = SOFT_RED, "Slow"
            vt = Text()
            vt.append(f"{mins:.1f}m", style=f"bold {color}")
            vt.append(f"  {label}", style=f"{color}")
            tbl.add_row("Epoch Avg", vt)

        # 24h avg block time
        if bts.get('avg_24h'):
            avg24 = bts['avg_24h']
            mins24 = avg24 / 60
            if avg24 < 540:
                color = NEON_GREEN
            elif avg24 <= 660:
                color = SOFT_GREEN
            else:
                color = SOFT_RED
            tbl.add_row("24h Avg", Text(f"{mins24:.1f}m", style=f"bold {color}"))

        # Next difficulty adjustment estimate
        if da.get('change'):
            change = da['change']
            color = NEON_GREEN if change >= 0 else SOFT_RED
            ct = Text()
            ct.append(f"{change:+.2f}%", style=f"bold {color}")
            tbl.add_row("Next Adj", ct)

        return tbl

    def render(self) -> Panel:
        if not self.block_height:
            return Panel(Text("  Waiting\u2026", style="dim italic"),
                         title=f"[bold {BTC_ORANGE}]\u26cf BLOCK HEIGHT[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        # Available width inside the panel (borders + padding ≈ 4)
        card_w = self.size.width - 4 if self.size.width > 0 else 120
        use_figlet = card_w >= 40

        if use_figlet:
            try:
                fig = pyfiglet.Figlet(font=self.figlet_font)
                height_str = str(self.block_height)
                raw = fig.renderText(height_str)
                lines = [ln for ln in raw.split('\n') if ln.strip()]
                max_w = max((len(ln) for ln in lines), default=0)
                # If figlet output is wider than the card, fall back
                if max_w > card_w * 0.6:
                    use_figlet = False
                else:
                    lines = [ln.ljust(max_w) for ln in lines]
                    large_text = '\n'.join(lines)
            except Exception:
                use_figlet = False

        # Left side: block height display
        left = Text()
        if use_figlet:
            for line in large_text.split('\n'):
                left.append(line + '\n', style=f"bold {BTC_ORANGE}")
        else:
            left.append(f"\n  {self.block_height:,}\n",
                        style=f"bold {BTC_ORANGE}")

        # Time since last block — green <10m, yellow 10-20m, red >20m
        if self.last_block_time > 0 and not self.is_ibd:
            secs = int(time.time() - self.last_block_time)
            if secs < 0:
                secs = 0
            if secs < 600:
                color = NEON_GREEN
            elif secs < 1200:
                color = SOFT_YELLOW
            else:
                color = SOFT_RED
            left.append(f" Last block: {_format_time_ago(secs)}",
                        style=f"bold {color}")
        elif self.is_ibd:
            left.append(" Syncing\u2026", style=f"bold {SOFT_YELLOW}")

        # Build layout: block height on left, epoch stats on right
        has_stats = (self.block_time_stats or self.diff_adj) and not self.is_ibd
        if has_stats and card_w >= 50:
            layout = Table.grid(padding=(0, 2), expand=True)
            layout.add_column("block", ratio=1)
            layout.add_column("stats", ratio=1)
            layout.add_row(left, self._build_epoch_stats())
        else:
            layout = left

        return Panel(layout,
                     title=f"[bold {BTC_ORANGE}]\u26cf BLOCK HEIGHT[/]",
                     border_style=BTC_ORANGE, box=box.ROUNDED)


class SatoshiCard(Static):
    """Rotating Satoshi Nakamoto quotes — inspired by warden_terminal"""

    ROTATE_SECS = 30  # advance quote every ~30 seconds

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._quote_idx = random.randint(0, len(SATOSHI_QUOTES) - 1)
        self._last_rotate = time.monotonic()

    def maybe_rotate(self):
        """Advance quote if enough time has passed, then refresh."""
        now = time.monotonic()
        if now - self._last_rotate >= self.ROTATE_SECS:
            self._last_rotate = now
            self._quote_idx = (self._quote_idx + 1) % len(SATOSHI_QUOTES)
        self.refresh()

    def render(self) -> Panel:
        q = SATOSHI_QUOTES[self._quote_idx]

        t = Text()
        t.append("\u201c", style=f"bold {BTC_ORANGE}")
        t.append(q['text'], style="italic white")
        t.append("\u201d", style=f"bold {BTC_ORANGE}")
        t.append(f"\n\n\u2014 Satoshi Nakamoto", style=f"bold {BTC_ORANGE}")
        t.append(f"\n  {q['date']}", style="dim")
        t.append(f"  \u2022  {q['source']}", style="dim")

        return Panel(t,
                     title=f"[bold {BTC_ORANGE}]\u2726 SATOSHI[/]",
                     subtitle=f"[dim]{self._quote_idx + 1}"
                              f"/{len(SATOSHI_QUOTES)}[/]",
                     border_style=BTC_ORANGE, box=box.ROUNDED)


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
        self.block_time_stats: Dict[str, Any] = {}

    def update_data(self, blockchain: Dict, hashrate: Dict = None,
                    diff_adj: Dict = None,
                    last_block_time: int = 0,
                    block_time_stats: Dict[str, Any] = None):
        self.data = {
            'difficulty': blockchain.get('difficulty', 0),
            'mediantime': blockchain.get('mediantime', 0),
            'last_block_time': last_block_time,
            'bestblockhash': blockchain.get('bestblockhash', ''),
            'warnings': blockchain.get('warnings', ''),
            'ibd': blockchain.get('initialblockdownload', False),
            'blocks': blockchain.get('blocks', 0),
        }
        self.hashrate_data = hashrate or {}
        self.diff_adj = diff_adj or {}
        if block_time_stats is not None:
            self.block_time_stats = block_time_stats
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

        # Fee revenue as % of block reward
        fee_pct = self.block_time_stats.get('avg_fee_pct')
        if fee_pct is not None:
            ft = Text()
            fc = NEON_GREEN if fee_pct < 10 else (
                SOFT_YELLOW if fee_pct < 50 else BTC_ORANGE)
            ft.append(f"{fee_pct:.1f}%", style=f"bold {fc}")
            ft.append(" of reward", style="dim")
            t.add_row("Fee/Rwd", ft)

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

        # Last block time — use actual block time, fall back to mediantime
        bt = self.data.get('last_block_time', 0)
        mt = bt if bt > 0 else self.data.get('mediantime', 0)
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
                         title=f"[bold {BTC_ORANGE}]1/2 HALVING[/]",
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

        return Panel(t, title=f"[bold {BTC_ORANGE}]1/2 HALVING[/]",
                     border_style=BTC_ORANGE, box=box.ROUNDED)


class RPCCard(Static):
    """RPC connection monitor — parsed from debug.log"""

    RPC_COLOR = "#FF6E40"  # deep orange for RPC

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data: Dict[str, Any] = {}

    def update_data(self, rpc_stats: Dict):
        self.data = rpc_stats
        self.refresh()

    def render(self) -> Panel:
        rpc_col = self.RPC_COLOR

        if not self.data or not self.data.get('has_data', False):
            content = Text()
            content.append("  No RPC log data found\n",
                           style="dim italic")
            content.append("  Enable debug=http in\n",
                           style="dim")
            content.append("  bitcoin.conf for full\n",
                           style="dim")
            content.append("  RPC monitoring\n\n", style="dim")
            content.append("  Press ", style="dim")
            content.append("d", style=f"bold {NEON_GREEN}")
            content.append(" to enable", style="dim")
            return Panel(content,
                         title=f"[bold {rpc_col}]\u2692 RPC[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        d = self.data

        # Total requests
        total = d.get('total_accepted', 0)
        ct = Text()
        ct.append(f"{total:,}", style="bold white")
        ct.append(" total", style="dim")
        t.add_row("Requests", ct)

        # Connections by time window
        a1h = d.get('accepts_1h', 0)
        a24h = d.get('accepts_24h', 0)
        if a1h > 0 or a24h > 0:
            wt = Text()
            wt.append(str(a1h), style="bold white")
            wt.append(" 1h", style="dim")
            wt.append(f"  {a24h}", style="bold white")
            wt.append(" 24h", style="dim")
            t.add_row("Accepted", wt)

        # Connection rate
        rate = d.get('conn_rate_per_min', 0)
        if rate > 0:
            rt = Text()
            rt.append(f"{rate:.1f}", style="bold white")
            rt.append("/min", style="dim")
            t.add_row("Rate", rt)

        # Last connection time
        last_ts = d.get('last_conn_ts', 0)
        if last_ts > 0:
            import time as _time
            ago = int(_time.time() - last_ts)
            lt = Text()
            lt.append(_format_time_ago(ago), style=f"bold {NEON_GREEN}")
            t.add_row("Last", lt)

        # Unique IPs
        ips_1h = d.get('unique_ips_1h', 0)
        ips_all = d.get('unique_ips_all', 0)
        if ips_all > 0:
            it = Text()
            it.append(str(ips_1h), style="bold white")
            it.append(" 1h", style="dim")
            it.append(f"  {ips_all}", style=f"bold {rpc_col}")
            it.append(" all", style="dim")
            t.add_row("IPs", it)

        # Top client IPs (show top 3 inline)
        top_ips = d.get('top_ips', [])
        for ip, info in top_ips[:3]:
            ipt = Text()
            ipt.append(ip, style=f"bold {CYAN}")
            ipt.append(f" \u00d7{info['count']:,}", style="dim")
            t.add_row("", ipt)

        # RPC calls in last hour
        calls_1h = d.get('total_calls_1h', 0)
        if calls_1h > 0:
            t.add_row("Calls/1h",
                       Text(f"{calls_1h:,}", style="bold white"))

        # Top methods (compact: show top 3)
        top = d.get('top_methods', [])
        if top:
            mt = Text()
            for i, (method, count) in enumerate(top[:3]):
                if i:
                    mt.append("  ", style="default")
                mt.append(method, style=f"bold {CYAN}")
                mt.append(f":{count}", style="dim")
            t.add_row("Methods", mt)

        # Auth failures
        fails_1h = d.get('auth_fails_1h', 0)
        fails_all = d.get('auth_fails_all', 0)
        if fails_all > 0:
            ft = Text()
            if fails_1h > 0:
                ft.append(str(fails_1h), style=f"bold {SOFT_RED}")
                ft.append(" 1h", style="dim")
                ft.append("  ", style="default")
            ft.append(str(fails_all), style=f"bold {SOFT_RED}")
            ft.append(" total", style="dim")
            t.add_row("AuthFail", ft)

            # Show last few failure details
            recent = d.get('recent_auth_fails', [])
            for detail in recent[-3:]:
                # Trim timestamp prefix for compact display
                short = detail
                if ']' in short:
                    short = short.split(']', 1)[-1].strip()
                elif 'Z' in short[:25]:
                    short = short[25:].strip()
                if len(short) > 50:
                    short = short[:47] + '...'
                dt = Text()
                dt.append("  \u2022 ", style="dim")
                dt.append(short, style=f"{SOFT_RED}")
                t.add_row("", dt)
        else:
            t.add_row("AuthFail",
                       Text("\u2713 none", style=f"bold {NEON_GREEN}"))

        # Security alerts
        alerts = d.get('alerts', [])
        for alert in alerts[:2]:
            level = alert.get('level', 'info')
            msg = alert.get('msg', '')
            color = SOFT_RED if level in ('warning', 'critical') \
                else SOFT_YELLOW
            at = Text()
            at.append("\u26a0 ", style=f"bold {color}")
            at.append(msg, style=color)
            t.add_row("Alert", at)

        border = SOFT_RED if fails_1h > 0 else rpc_col
        return Panel(t,
                     title=f"[bold {rpc_col}]\u2692 RPC[/]",
                     border_style=border, box=box.ROUNDED)


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

        cpu_temp = self.data.get('cpu_temp')
        if cpu_temp is not None:
            temp_color = NEON_GREEN if cpu_temp < 65 else (
                SOFT_YELLOW if cpu_temp < 80 else SOFT_RED)
            tt = Text()
            tt.append(f"{cpu_temp:.0f}°C", style=f"bold {temp_color}")
            t.add_row("Temp", tt)

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

        # Primary disk (Bitcoin data volume if available)
        dp = self.data.get('disk_percent', 0)
        disk_used = self.data.get('disk_used', 0)
        disk_total = self.data.get('disk_total', 0)
        disk_label = self.data.get('disk_label', '/')
        lbl = "Disk \u20bf" if disk_label != '/' else "Disk /"
        disk_color = NEON_GREEN if dp < 75 else (
            SOFT_YELLOW if dp < 90 else SOFT_RED)
        t.add_row(lbl, _make_bar(dp, width=15, fill_color=disk_color))
        dt = Text()
        dt.append(f"{format_bytes(disk_used)}", style="white")
        dt.append(f" / {format_bytes(disk_total)}", style="dim")
        t.add_row("", dt)

        # Secondary: root / (only if different volume)
        rdp = self.data.get('root_disk_percent')
        if rdp is not None:
            rd_used = self.data.get('root_disk_used', 0)
            rd_total = self.data.get('root_disk_total', 0)
            rd_color = NEON_GREEN if rdp < 75 else (
                SOFT_YELLOW if rdp < 90 else SOFT_RED)
            t.add_row("Disk /",
                       _make_bar(rdp, width=15, fill_color=rd_color))
            rdt = Text()
            rdt.append(f"{format_bytes(rd_used)}", style="white")
            rdt.append(f" / {format_bytes(rd_total)}", style="dim")
            t.add_row("", rdt)

        return Panel(t, title=f"[bold {DIM_BORDER}]\u2699 SYSTEM[/]",
                     border_style=DIM_BORDER, box=box.ROUNDED)


class MarketCard(Static):
    """Market data: cap, ATH, block subsidy, supply"""

    MARKET_COLOR = "#E040FB"  # pink-purple

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.price_data: Dict[str, Any] = {}
        self.block_height: int = 0

    def update_data(self, price: Dict, block_height: int = 0):
        self.price_data = price
        self.block_height = block_height
        self.refresh()

    def render(self) -> Panel:
        mc = self.MARKET_COLOR
        if not self.price_data:
            return Panel(Text("  Loading market data\u2026", style="dim italic"),
                         title=f"[bold {mc}]\u2261 MARKET[/]",
                         border_style=DIM_BORDER, box=box.ROUNDED)

        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column("K", style="dim", width=10)
        t.add_column("V", style="white")

        usd = self.price_data.get('usd', 0)

        # Market cap
        mcap = self.price_data.get('usd_market_cap', 0)
        if mcap > 0:
            if mcap >= 1e12:
                cap_str = f"${mcap / 1e12:.2f}T"
            elif mcap >= 1e9:
                cap_str = f"${mcap / 1e9:.1f}B"
            else:
                cap_str = f"${mcap / 1e6:.0f}M"
            t.add_row("Mkt Cap", Text(cap_str, style=f"bold {NEON_GREEN}"))

        # All-time high
        ath = self.price_data.get('ath_usd', 0)
        if ath > 0:
            at = Text()
            at.append(f"${ath:,.0f}", style="bold white")
            t.add_row("ATH", at)

            # Decline from ATH
            ath_pct = self.price_data.get('ath_change_pct', 0)
            if ath_pct:
                dt = Text()
                if ath_pct < 0:
                    dt.append(f"{ath_pct:.1f}%", style=f"bold {SOFT_RED}")
                else:
                    dt.append(f"+{ath_pct:.1f}%", style=f"bold {NEON_GREEN}")
                dt.append(" from ATH", style="dim")
                t.add_row("", dt)

            # ATH date and days since
            ath_date_str = self.price_data.get('ath_date', '')
            if ath_date_str:
                try:
                    from datetime import datetime as _dt
                    ath_dt = _dt.fromisoformat(
                        ath_date_str.replace('Z', '+00:00'))
                    from datetime import timezone
                    now_utc = _dt.now(timezone.utc)
                    days_since = (now_utc - ath_dt).days
                    dd = Text()
                    dd.append(ath_dt.strftime("%b %d, %Y"), style="white")
                    dd.append(f"  ({days_since:,}d)", style="dim")
                    t.add_row("ATH Date", dd)
                except (ValueError, TypeError):
                    pass

        # Block subsidy
        if self.block_height > 0:
            sub_btc = block_subsidy(self.block_height)
            st = Text()
            st.append(f"{sub_btc:.4g} BTC", style=f"bold {BTC_ORANGE}")
            if usd > 0:
                sub_usd = sub_btc * usd
                st.append(f"  ${sub_usd:,.0f}", style=SOFT_GREEN)
            t.add_row("Subsidy", st)

        # Supply: mined / remaining / progress
        if self.block_height > 0:
            mined = total_mined(self.block_height)
            remaining = MAX_SUPPLY - mined
            mt = Text()
            mt.append(f"{mined:,.0f}", style="bold white")
            mt.append(" BTC", style="dim")
            t.add_row("Mined", mt)

            rt = Text()
            rt.append(f"{remaining:,.0f}", style=f"bold {SOFT_YELLOW}")
            rt.append(" BTC", style="dim")
            t.add_row("Remaining", rt)

            pct = mined / MAX_SUPPLY * 100
            t.add_row("Supply",
                       _make_bar(pct, width=15, fill_color=BTC_ORANGE))

        return Panel(t, title=f"[bold {mc}]\u2261 MARKET[/]",
                     border_style=mc, box=box.ROUNDED)


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


# ── Matrix Rain Animation ──────────────────────────────────────────────

_MATRIX_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "@#$%^&*+-=<>~"
    "\uff8a\uff90\uff8b\uff70\uff73\uff7c\uff85\uff93\uff86\uff7b\uff9c\uff82\uff75\uff98\uff71\uff8e\uff83\uff8f\uff79\uff92\uff74\uff76\uff77\uff91\uff95\uff97\uff7e\uff88\uff7d\uff80\uff87\uff8d"
)

# Green gradient: bright head → dark tail  (fg on transparent bg)
_RAIN_STYLES_FG = [
    "#ffffff",   # 0 – head (white-hot)
    "#00ff41",   # 1 – bright green
    "#00dd33",   # 2
    "#00aa22",   # 3
    "#007718",   # 4
    "#004d10",   # 5
    "#003308",   # 6 – very dim
]

# Fade-in scrim colours (from nearly invisible → dark)
_SCRIM_LEVELS = [
    "rgba(0,0,0,0.0)",
    "rgba(0,0,0,0.15)",
    "rgba(0,0,0,0.30)",
    "rgba(0,0,0,0.45)",
    "rgba(0,0,0,0.58)",
    "rgba(0,0,0,0.68)",
    "rgba(0,0,0,0.75)",
]


class _RainCanvas(Static):
    """Custom widget that only paints rain characters; blank cells are
    fully transparent so the dashboard underneath shows through."""

    DEFAULT_CSS = """
    _RainCanvas {
        width: 100%;
        height: 100%;
        background: transparent;
    }
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._frame: Text = Text("")

    def set_frame(self, frame: Text) -> None:
        self._frame = frame
        self.refresh()

    def render(self) -> Text:
        return self._frame


class MatrixRainScreen(ModalScreen):
    """Full-screen Matrix code-rain overlay triggered on new block.

    The animation goes *over* the current dashboard:
    • Phase 1 (0-0.8s)  – sparse glitch flicker fades in
    • Phase 2 (0.8-4.2s) – full rain streams
    • Phase 3 (4.2-5.0s) – rain thins out, dashboard reappears
    The scrim (dark tint) fades in/out so the dashboard is always
    partially visible underneath.
    """

    DURATION = 5.0  # seconds
    _FADE_IN = 0.8   # seconds to ramp up
    _FADE_OUT = 0.8   # seconds to ramp down

    DEFAULT_CSS = """
    MatrixRainScreen {
        background: transparent;
    }
    """

    def __init__(self, block_height: int = 0,
                 banner_text: str = "") -> None:
        super().__init__()
        self.block_height = block_height
        self.banner_text = banner_text or f"  \u26cf  NEW BLOCK {block_height:,}  \u26cf  "
        self._drops: list = []
        self._cols = 0
        self._rows = 0
        self._start = 0.0
        self._grid: list = []
        self._canvas: _RainCanvas | None = None
        self._dismissed = False
        self._timer = None

    def compose(self) -> ComposeResult:
        self._canvas = _RainCanvas()
        yield self._canvas

    def on_mount(self) -> None:
        self._start = time.monotonic()
        size = self.app.size
        self._cols = max(size.width, 20)
        self._rows = max(size.height, 10)

        rc = random.choice
        mc = _MATRIX_CHARS
        self._grid = [
            [rc(mc) for _ in range(self._cols)]
            for _ in range(self._rows)
        ]

        # Stagger drops — some already mid-screen for instant visual
        self._drops = []
        for _ in range(self._cols):
            self._drops.append({
                'y': random.uniform(-self._rows * 0.5, self._rows * 0.3),
                'speed': random.uniform(0.4, 1.8),
                'length': random.randint(4, min(22, self._rows)),
                'active': True,
            })

        # Render first frame immediately so there's no blank flash
        self._canvas.set_frame(self._render_frame(0.0))
        self._timer = self.set_interval(1 / 16, self._tick)

    def _tick(self) -> None:
        if self._dismissed:
            return
        elapsed = time.monotonic() - self._start
        if elapsed >= self.DURATION:
            self._dismissed = True
            if self._timer:
                self._timer.stop()
            self.dismiss()
            return

        # Advance drops
        for drop in self._drops:
            if not drop['active']:
                continue
            drop['y'] += drop['speed']
            if drop['y'] - drop['length'] > self._rows:
                # During fade-out, don't respawn — let screen clear
                if elapsed > self.DURATION - self._FADE_OUT:
                    drop['active'] = False
                    continue
                drop['y'] = random.uniform(-8, -1)
                drop['speed'] = random.uniform(0.4, 1.8)
                drop['length'] = random.randint(4, min(22, self._rows))

        # Flicker: mutate random chars
        rc = random.choice
        ri = random.randint
        mc = _MATRIX_CHARS
        for _ in range(self._cols // 3):
            self._grid[ri(0, self._rows - 1)][ri(0, self._cols - 1)] = rc(mc)

        self._canvas.set_frame(self._render_frame(elapsed))

        # Fade scrim in/out by adjusting screen background
        scrim = self._scrim_for(elapsed)
        self.styles.background = scrim

    def _scrim_for(self, elapsed: float) -> str:
        """Return a scrim colour based on the animation phase."""
        n = len(_SCRIM_LEVELS) - 1
        if elapsed < self._FADE_IN:
            # Fade in
            t = elapsed / self._FADE_IN
            idx = int(t * n)
        elif elapsed > self.DURATION - self._FADE_OUT:
            # Fade out
            remaining = self.DURATION - elapsed
            t = remaining / self._FADE_OUT
            idx = int(t * n)
        else:
            idx = n  # full scrim
        return _SCRIM_LEVELS[min(idx, n)]

    def _density_for(self, elapsed: float) -> float:
        """Fraction of columns that should show rain (0.0–1.0)."""
        if elapsed < self._FADE_IN:
            return elapsed / self._FADE_IN
        if elapsed > self.DURATION - self._FADE_OUT:
            return max(0.0, (self.DURATION - elapsed) / self._FADE_OUT)
        return 1.0

    def _render_frame(self, elapsed: float) -> Text:
        cols, rows = self._cols, self._rows
        n_styles = len(_RAIN_STYLES_FG)
        density = self._density_for(elapsed)

        # Determine which columns are "active" at current density
        # Use a stable per-column hash so columns don't flicker on/off
        active_cols = set()
        for c in range(cols):
            # Threshold based on column's hash position
            if ((c * 7 + 3) % cols) / cols < density:
                active_cols.add(c)

        # Glitch phase: random scattered single characters
        glitch_cells: set = set()
        if elapsed < self._FADE_IN:
            glitch_pct = 0.03 * (elapsed / self._FADE_IN)
            n_glitch = int(rows * cols * glitch_pct)
            ri = random.randint
            for _ in range(n_glitch):
                glitch_cells.add((ri(0, rows - 1), ri(0, cols - 1)))

        # Build per-cell style index
        style_map = [[-1] * cols for _ in range(rows)]
        for c, drop in enumerate(self._drops):
            if c not in active_cols or not drop['active']:
                continue
            head_y = int(drop['y'])
            length = drop['length']
            for i in range(length):
                r = head_y - i
                if 0 <= r < rows:
                    idx = int(i / length * n_styles)
                    idx = min(idx, n_styles - 1)
                    cur = style_map[r][c]
                    if cur == -1 or idx < cur:
                        style_map[r][c] = idx

        # Add glitch cells (bright green flicker)
        for gr, gc in glitch_cells:
            if style_map[gr][gc] == -1:
                style_map[gr][gc] = 1  # bright green

        # Banner
        banner = self.banner_text
        show_banner = elapsed > 0.5
        banner_row = rows // 2
        banner_start = max(0, (cols - len(banner)) // 2)
        banner_end = min(cols, banner_start + len(banner))
        pulse = 1.0 if int(elapsed * 6) % 2 == 0 else 0.7

        grid = self._grid
        output = Text()
        for r in range(rows):
            if r > 0:
                output.append("\n")
            row_styles = style_map[r]
            row_chars = grid[r]
            is_banner_row = show_banner and r == banner_row

            c = 0
            while c < cols:
                # Banner region
                if is_banner_row and banner_start <= c < banner_end:
                    bi = c - banner_start
                    if pulse > 0.9:
                        output.append(banner[bi],
                                      style=f"bold {BTC_ORANGE} on #1a0a00")
                    else:
                        output.append(banner[bi],
                                      style=f"{BTC_ORANGE} on #1a0a00")
                    c += 1
                    continue

                si = row_styles[c]
                if si >= 0:
                    # Rain character — draw with colour, NO background
                    bold = "bold " if si == 0 else ""
                    run = [row_chars[c]]
                    style_str = f"{bold}{_RAIN_STYLES_FG[si]}"
                    j = c + 1
                    while j < cols:
                        if is_banner_row and j >= banner_start:
                            break
                        if row_styles[j] != si:
                            break
                        run.append(row_chars[j])
                        j += 1
                    output.append("".join(run), style=style_str)
                else:
                    # Blank cell — space with NO style → transparent
                    j = c + 1
                    while j < cols:
                        if is_banner_row and j >= banner_start:
                            break
                        if row_styles[j] != -1:
                            break
                        j += 1
                    output.append(" " * (j - c))
                c = j

        return output

    def on_key(self, event) -> None:
        """Any key press dismisses the animation early."""
        if self._dismissed:
            return
        self._dismissed = True
        if self._timer:
            self._timer.stop()
        self.dismiss()


# ── Confirm Debug Modal ────────────────────────────────────────────────

class ConfirmDebugScreen(ModalScreen[bool]):
    """Modal asking user to enable debug=http in bitcoin.conf."""

    CSS = """
    ConfirmDebugScreen {
        align: center middle;
    }
    #debug-dialog {
        width: 64;
        height: auto;
        border: thick $accent;
        background: #111111;
        padding: 1 2;
    }
    #debug-dialog Static {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    #debug-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
    }
    #debug-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(self, conf_path: Path) -> None:
        super().__init__()
        self.conf_path = conf_path

    def compose(self) -> ComposeResult:
        with Vertical(id="debug-dialog"):
            yield Static(
                f"[bold {BTC_ORANGE}]Enable RPC Debug Logging?[/]\n\n"
                f"This will add [bold]debug=http[/] to:\n"
                f"[dim]{self.conf_path}[/]\n\n"
                f"and activate it immediately via RPC."
            )
            with Center(id="debug-buttons"):
                yield Button("Yes, enable", variant="success", id="btn-yes")
                yield Button("Cancel", variant="error", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")


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
    #dashboard-grid {
        layout: grid;
        grid-gutter: 1;
    }
    .card {
        height: 100%;
        overflow-y: auto;
    }
    Footer {
        background: #111111;
    }
    """

    BINDINGS = [
        ("q", "quit",          "Quit"),
        ("R", "refresh",       "Refresh"),
        ("r", "rain",          "Rain"),
        ("c", "toggle_config", "Config"),
        ("l", "view_logs",     "Logs"),
        ("s", "display_settings", "Display"),
        ("d", "enable_rpc_debug", "Debug"),
    ]

    def __init__(self, datadir: Optional[str] = None):
        super().__init__()
        self.config = Config()
        self.datadir = Path(datadir) if datadir else self.config.get_datadir()
        self.rpc: Optional[BitcoinRPC] = None
        self._refresh_interval = self.config.get_display_config().get(
            'refresh_interval', 5)
        self._sync_tracker = SyncTracker()
        self._peer_tracker = PeerTracker()
        self._rpc_monitor = RPCMonitor()
        self._shutting_down = False
        self._last_block_height: int = 0
        self._block_time_stats: Dict[str, Any] = {}
        self._show_startup_rain = True
        self._rain_screen_active = False
        self._current_layout: Optional[int] = None
        self._display_settings = load_display_settings()
        self._last_good_data: Optional[Dict[str, Any]] = None
        self._consecutive_errors: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield BitcoinHeader()
        self.status_bar = StatusBar()
        yield self.status_bar

        with Grid(id="dashboard-grid"):
            # Hero row: Block Height (spans 2 cols) | Price
            self.block_height_card = BlockHeightCard(
                classes="card", id="large-block-height")
            yield self.block_height_card
            self.price_card = PriceCard(classes="card")
            yield self.price_card

            # Row 1: Node | Network | Market
            self.node_card = NodeCard(classes="card")
            yield self.node_card
            self.network_card = NetworkCard(classes="card")
            yield self.network_card
            self.market_card = MarketCard(classes="card")
            yield self.market_card

            # Row 2: Mempool | Blockchain | Halving
            self.mempool_card = MempoolCard(classes="card")
            yield self.mempool_card
            self.blockchain_card = BlockchainCard(classes="card")
            yield self.blockchain_card
            self.halving_card = HalvingCard(classes="card")
            yield self.halving_card

            # Row 3: RPC | System | Satoshi Quotes
            self.rpc_card = RPCCard(classes="card")
            yield self.rpc_card
            self.system_card = SystemCard(classes="card")
            yield self.system_card
            self.satoshi_card = SatoshiCard(classes="card")
            yield self.satoshi_card

        yield Footer()

    def _apply_layout(self, width: int, height: int) -> None:
        """Adjust grid columns/rows based on terminal size."""
        if width >= 120:
            cols = 3
        elif width >= 80:
            cols = 2
        else:
            cols = 1

        if cols == self._current_layout:
            return
        self._current_layout = cols

        grid = self.query_one("#dashboard-grid")
        hero = self.block_height_card

        grid.styles.grid_size_columns = cols

        if cols == 3:
            # 4 rows: hero(9) + 3×1fr
            hero.styles.column_span = 2
            grid.styles.grid_size_rows = 4
            grid.styles.grid_rows = "9 1fr 1fr 1fr"
            grid.styles.overflow_y = "hidden"
        elif cols == 2:
            # 6 rows: hero(7) + 5×1fr
            hero.styles.column_span = 2
            grid.styles.grid_size_rows = 6
            grid.styles.grid_rows = "7 1fr 1fr 1fr 1fr 1fr"
            grid.styles.overflow_y = "auto"
        else:
            # 1 col, all stacked, scrollable
            hero.styles.column_span = 1
            grid.styles.grid_size_rows = 11
            grid.styles.grid_rows = "7 " + " ".join(["1fr"] * 10)
            grid.styles.overflow_y = "auto"

    def on_resize(self, event) -> None:
        self._apply_layout(event.size.width, event.size.height)

    def on_mount(self) -> None:
        self.title = "Bitcoin Terminal"
        self.sub_title = str(self.datadir) if self.datadir else "No datadir"

        self._apply_display_settings()
        self._apply_layout(self.size.width, self.size.height)

        if self.datadir and self.datadir.exists():
            env_rpc = self.config.get_rpc_config()
            self.rpc = BitcoinRPC.from_datadir(self.datadir,
                                                env_config=env_rpc)
            # Point RPC monitor at debug.log
            log_path = self._get_log_path()
            self._rpc_monitor.set_log_path(log_path)

        self.refresh_data()
        self.set_interval(self._refresh_interval, self.refresh_data)

    def refresh_data(self) -> None:
        if self.rpc and not self._shutting_down:
            self.run_worker(self._fetch_and_update, thread=True,
                            exclusive=True)

    def _fetch_and_update(self) -> None:
        if not self.rpc or self._shutting_down:
            return
        data = _fetch_all_data(self.rpc,
                               datadir=str(self.datadir)
                               if self.datadir else None)
        # Update P2P peer tracker (thread-safe: only called from worker)
        peers = data.get('peers', [])
        network = data.get('network', {})
        if peers or network:
            data['peer_stats'] = self._peer_tracker.update(peers, network)
        # Update RPC monitor from debug.log
        data['rpc_stats'] = self._rpc_monitor.update()
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
            self._consecutive_errors += 1
            # On transient errors, reuse last good data for up to 6
            # cycles (~30s) so the UI doesn't flash CONNECTION FAILED
            # every refresh while the node is briefly busy.
            if (self._last_good_data is not None
                    and self._consecutive_errors <= 6):
                data = self._last_good_data
                # Re-extract all fields from the cached good data
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
            else:
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
        else:
            self._consecutive_errors = 0
            self._last_good_data = data

        is_ibd = blockchain.get('initialblockdownload', False)
        blocks = blockchain.get('blocks', 0)
        headers = blockchain.get('headers', 0)
        sync_info = self._sync_tracker.update(blocks, headers)

        # Consider "catching up" if >3 blocks behind headers,
        # even after IBD is complete (e.g. node was offline for hours)
        catching_up = headers > 0 and (headers - blocks) > 3

        # Startup rain on first successful load
        if self._show_startup_rain and blocks > 0:
            self._show_startup_rain = False
            self._last_block_height = blocks
            if not catching_up:
                self._rain_screen_active = True
                self.push_screen(
                    MatrixRainScreen(
                        block_height=blocks,
                        banner_text="  \u20bf  Welcome to Bitcoin Node Terminal  \u20bf  ",
                    ),
                    callback=lambda _: setattr(self, '_rain_screen_active', False),
                )
        else:
            # Detect new block (skip during IBD, catch-up, and first load)
            if (blocks > 0
                    and self._last_block_height > 0
                    and blocks > self._last_block_height
                    and not is_ibd
                    and not catching_up
                    and not self._rain_screen_active):
                self._rain_screen_active = True
                self.push_screen(
                    MatrixRainScreen(block_height=blocks),
                    callback=lambda _: setattr(self, '_rain_screen_active', False),
                )
            self._last_block_height = blocks

        # ── Block timing stats & derived metrics (compute early) ──
        bts = data.get('block_time_stats')
        if bts:
            self._block_time_stats = bts

        usd = price.get('usd', 0)
        net_hashrate = hashrate.get('hashrate', 0)  # H/s
        if usd > 0 and net_hashrate > 0 and headers > 0:
            subsidy = block_subsidy(headers)
            daily_rev = subsidy * 144 * usd
            hashrate_ph = net_hashrate / 1e15  # H/s -> PH/s
            if hashrate_ph > 0:
                self._block_time_stats['hashprice'] = daily_rev / hashrate_ph

        hr_ath = hashrate.get('hashrate_ath', 0)
        if hr_ath > 0 and net_hashrate > 0:
            self._block_time_stats['hashrate_ath'] = hr_ath
            self._block_time_stats['hashrate_dd'] = (
                (1 - net_hashrate / hr_ath) * 100)

        # ── Update cards ──
        self.node_card.update_data(blockchain, network, uptime,
                                   sync_info=sync_info,
                                   last_block_time=data.get(
                                       'last_block_time', 0))
        conn_stats = data.get('peer_stats', {})
        self.network_card.update_data(network, peers, conn_stats=conn_stats)
        self.mempool_card.update_data(mempool, is_ibd=is_ibd)
        self.blockchain_card.update_data(blockchain, hashrate=hashrate,
                                         diff_adj=diff_adj,
                                         last_block_time=data.get(
                                             'last_block_time', 0),
                                         block_time_stats=self._block_time_stats)
        self.price_card.update_data(price, fees=fees,
                                    block_time_stats=self._block_time_stats)
        self.system_card.update_data(system)

        # Market card (market cap, ATH, subsidy, supply)
        self.market_card.update_data(price, block_height=blocks)

        # Block height hero card (with epoch stats)
        self.block_height_card.update_data(
            blocks,
            last_block_time=data.get('last_block_time', 0),
            is_ibd=is_ibd,
            block_time_stats=self._block_time_stats,
            diff_adj=diff_adj,
        )

        # Rotate Satoshi quote
        self.satoshi_card.maybe_rotate()

        # RPC monitor
        rpc_stats = data.get('rpc_stats', {})
        self.rpc_card.update_data(rpc_stats)

        # Halving: use headers (network tip) so number is correct
        # even during initial sync
        if headers > 0:
            self.halving_card.update_data(headers)

        # Status bar — also check blocks vs headers to avoid
        # showing SYNCED when the node is still catching up
        sync_pct = blockchain.get('verificationprogress', 0.0) * 100
        self.status_bar.sync_pct = sync_pct
        self.status_bar.chain = blockchain.get('chain', 'main')
        fully_synced = sync_pct >= 99.99 and not catching_up and not is_ibd
        self.status_bar.status = "synced" if fully_synced else "syncing"
        self.status_bar.blocks = blocks
        self.status_bar.peers = network.get('connections', 0)
        self.status_bar.btc_price = price.get('usd', 0)
        self.status_bar.epoch_avg = self._block_time_stats.get(
            'epoch_avg', 0) or 0.0
        self.status_bar.hashprice = self._block_time_stats.get(
            'hashprice', 0) or 0.0
        self.status_bar.fee_pct = self._block_time_stats.get(
            'avg_fee_pct', 0) or 0.0

    # ── Card name → attribute mapping for visibility ──
    _CARD_ATTR_MAP = {
        'block_height': 'block_height_card',
        'price': 'price_card',
        'node': 'node_card',
        'network': 'network_card',
        'market': 'market_card',
        'mempool': 'mempool_card',
        'blockchain': 'blockchain_card',
        'halving': 'halving_card',
        'rpc': 'rpc_card',
        'system': 'system_card',
        'satoshi': 'satoshi_card',
    }

    def _apply_display_settings(self) -> None:
        """Apply display settings to cards, fonts, and status bar."""
        ds = self._display_settings
        font = ds.get('figlet_font', 'small')
        self.price_card.figlet_font = font
        self.block_height_card.figlet_font = font

        # Card visibility
        vis_cards = ds.get('visible_cards', {})
        for key, attr in self._CARD_ATTR_MAP.items():
            card = getattr(self, attr, None)
            if card:
                card.display = vis_cards.get(key, True)

        # Status bar header visibility
        vis_header = ds.get('visible_header', {})
        self.status_bar.visible_items = vis_header

        # Refresh all visible cards
        for attr in self._CARD_ATTR_MAP.values():
            card = getattr(self, attr, None)
            if card and card.display:
                card.refresh()
        self.status_bar.refresh()

    def action_display_settings(self) -> None:
        """Open the display settings screen."""
        def on_return(result) -> None:
            self._display_settings = load_display_settings()
            self._apply_display_settings()
            self._current_layout = None  # force re-layout
            self._apply_layout(self.size.width, self.size.height)

        self.push_screen(DisplaySettingsScreen(), callback=on_return)

    def action_refresh(self) -> None:
        self.refresh_data()
        self.satoshi_card._quote_idx = (
            self.satoshi_card._quote_idx + 1) % len(SATOSHI_QUOTES)
        self.satoshi_card.refresh()
        self.notify("Refreshed", timeout=1)

    def action_rain(self) -> None:
        """Trigger Matrix code rain on demand."""
        height = self._last_block_height or 0
        self.push_screen(MatrixRainScreen(block_height=height))

    def action_toggle_config(self) -> None:
        if self.datadir:
            conf_path = self.datadir / 'bitcoin.conf'
            subversion = ''
            if self.node_card.data and isinstance(self.node_card.data, dict):
                subversion = self.node_card.data.get('subversion', '')
            system_metrics = getattr(self.system_card, 'data', {})
            block_time_stats = self._block_time_stats
            self.push_screen(ConfigScreen(conf_path, subversion,
                                          system_metrics, block_time_stats,
                                          rpc=self.rpc))

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

    def action_enable_rpc_debug(self) -> None:
        """Prompt to enable debug=http in bitcoin.conf."""
        if not self.datadir:
            self.notify("No data directory configured", severity="error")
            return
        conf_path = self.datadir / 'bitcoin.conf'
        # Check if already enabled
        if conf_path.exists():
            try:
                content = conf_path.read_text(encoding='utf-8')
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    if 'debug=http' in stripped or 'debug=1' in stripped:
                        self.notify("debug=http is already enabled",
                                    timeout=3)
                        return
            except OSError:
                pass

        def on_confirm(result: bool) -> None:
            if not result:
                return
            self._write_debug_http(conf_path)

        self.push_screen(
            ConfirmDebugScreen(conf_path=conf_path),
            callback=on_confirm,
        )

    def _write_debug_http(self, conf_path: Path) -> None:
        """Append debug=http to bitcoin.conf and activate via RPC."""
        try:
            with open(conf_path, 'a', encoding='utf-8') as f:
                f.write('\n# Added by Bitcoin Terminal — '
                        'enables RPC connection monitoring\n')
                f.write('debug=http\n')
        except OSError as e:
            self.notify(f"Failed to write config: {e}",
                        severity="error", timeout=5)
            return

        # Activate at runtime via RPC — no restart needed
        rpc_ok = False
        if self.rpc:
            try:
                self.rpc.call('logging', [["http"]])
                rpc_ok = True
            except Exception:
                pass

        if rpc_ok:
            self.notify(
                "debug=http enabled and activated live",
                title="\u2713 RPC Debug On",
                timeout=5,
            )
        else:
            self.notify(
                "Added debug=http to bitcoin.conf\n"
                "Restart bitcoind to apply",
                title="\u2713 Config Updated",
                timeout=8,
            )

        # Reload the config card if visible
        try:
            self.config_card.load_config()
            self.config_card.refresh()
        except Exception:
            pass


if __name__ == "__main__":
    app = BitcoinTUI()
    app.run()
