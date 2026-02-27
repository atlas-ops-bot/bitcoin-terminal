"""
Main TUI Application
Minimalistic ANSI BBS-inspired Bitcoin Node Monitor
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bitcoin_terminal.config import Config
from bitcoin_terminal.rpc import BitcoinRPC
from bitcoin_terminal.ansi_utils import *


class BitcoinHeader(Static):
    """Minimalistic header"""

    def on_mount(self) -> None:
        header = Text()
        header.append("[ ", style="dim")
        header.append("BITCOIN NODE MONITOR", style="bold white")
        header.append(" ]", style="dim")

        self.update(Panel(
            header,
            border_style="dim white",
            box=box.ASCII
        ))


class StatusBar(Static):
    """Single line status bar"""

    status = reactive("offline")
    blocks = reactive(0)
    peers = reactive(0)

    def render(self) -> Text:
        line = Text()

        # Status indicator
        if self.status == "synced":
            line.append("● ", style="green")
            line.append("SYNCED", style="green")
        elif self.status == "syncing":
            line.append("◐ ", style="yellow")
            line.append("SYNCING", style="yellow")
        else:
            line.append("○ ", style="dim")
            line.append("OFFLINE", style="dim")

        line.append(" | ", style="dim")
        line.append(f"Height: ", style="dim")
        line.append(jformat(self.blocks, 0), style="white")

        line.append(" | ", style="dim")
        line.append(f"Peers: ", style="dim")
        line.append(str(self.peers), style="white")

        line.append(" | ", style="dim")
        line.append(datetime.now().strftime("%H:%M:%S"), style="dim")

        return line


class NodeCard(Static):
    """Node health and sync information"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None
        self.data = {}

    def set_rpc(self, rpc: BitcoinRPC):
        self.rpc = rpc
        self.update_data()

    def update_data(self):
        if not self.rpc:
            return

        try:
            blockchain_info = self.rpc.getblockchaininfo()
            network_info = self.rpc.getnetworkinfo()
            uptime_seconds = self.rpc.uptime()

            self.data = {
                'blocks': blockchain_info.get('blocks', 0),
                'headers': blockchain_info.get('headers', 0),
                'chain': blockchain_info.get('chain', 'unknown'),
                'sync_pct': blockchain_info.get('verificationprogress', 0.0) * 100,
                'ibd': blockchain_info.get('initialblockdownload', False),
                'size_gb': blockchain_info.get('size_on_disk', 0) / (1024**3),
                'pruned': blockchain_info.get('pruned', False),
                'version': network_info.get('version', 0),
                'subversion': network_info.get('subversion', ''),
                'uptime': uptime_seconds,
            }
            self.refresh()
        except Exception as e:
            self.data = {'error': str(e)}
            self.refresh()

    def render(self) -> Panel:
        if 'error' in self.data:
            return Panel(
                error("CONNECTION FAILED") + "\n" + muted(self.data['error']),
                title=bold("NODE"),
                border_style="red",
                box=box.ASCII
            )

        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column("Key", style="dim", width=12)
        table.add_column("Value", style="white")

        # Status
        blocks = self.data.get('blocks', 0)
        headers = self.data.get('headers', 0)
        sync_pct = self.data.get('sync_pct', 0)

        if sync_pct >= 99.99:
            status = success("SYNCED")
        elif self.data.get('ibd', False):
            status = warning(f"SYNCING {sync_pct:.1f}%")
        else:
            behind = headers - blocks
            status = warning(f"{behind} BEHIND")

        table.add_row("Status", status)
        table.add_row("Chain", self.data.get('chain', '').upper())
        table.add_row("Height", jformat(blocks, 0) + muted(f" / {jformat(headers, 0)}"))
        table.add_row("Uptime", format_uptime(self.data.get('uptime', 0)))

        # Version
        version = self.data.get('version', 0)
        version_str = f"{version // 10000}.{(version // 100) % 100}.{version % 100}"
        table.add_row("Version", version_str)

        # Storage
        size_gb = self.data.get('size_gb', 0)
        storage = f"{size_gb:.0f} GB"
        if self.data.get('pruned', False):
            storage += " " + warning("PRUNED")
        table.add_row("Storage", storage)

        return Panel(
            table,
            title=bold("NODE"),
            border_style="green",
            box=box.ASCII
        )


class NetworkCard(Static):
    """Network connections"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None
        self.data = {}

    def set_rpc(self, rpc: BitcoinRPC):
        self.rpc = rpc
        self.update_data()

    def update_data(self):
        if not self.rpc:
            return

        try:
            network_info = self.rpc.getnetworkinfo()
            peer_info = self.rpc.getpeerinfo()

            # Connection types
            ipv4 = sum(1 for p in peer_info if ':' not in p.get('addr', '').split(':')[0])
            tor = sum(1 for p in peer_info if '.onion' in p.get('addr', ''))

            # Traffic
            rx_mb = sum(p.get('bytesrecv', 0) for p in peer_info) / (1024**2)
            tx_mb = sum(p.get('bytessent', 0) for p in peer_info) / (1024**2)

            self.data = {
                'connections': network_info.get('connections', 0),
                'connections_in': network_info.get('connections_in', 0),
                'connections_out': network_info.get('connections_out', 0),
                'ipv4': ipv4,
                'tor': tor,
                'rx_mb': rx_mb,
                'tx_mb': tx_mb,
            }
            self.refresh()
        except:
            self.data = {}
            self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(muted("NO DATA"), title=bold("NETWORK"), border_style="dim", box=box.ASCII)

        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column("Key", style="dim", width=12)
        table.add_column("Value", style="white")

        total = self.data.get('connections', 0)
        inbound = self.data.get('connections_in', 0)
        outbound = self.data.get('connections_out', 0)

        table.add_row("Peers", f"{total} " + muted(f"({inbound} in / {outbound} out)"))

        # Types
        ipv4 = self.data.get('ipv4', 0)
        tor = self.data.get('tor', 0)
        types = f"IPv4:{ipv4}"
        if tor > 0:
            types += muted(" | ") + f"Tor:{tor}"
        table.add_row("Types", types)

        # Traffic
        rx = self.data.get('rx_mb', 0)
        tx = self.data.get('tx_mb', 0)
        table.add_row("Traffic RX", f"{rx:.0f} MB")
        table.add_row("Traffic TX", f"{tx:.0f} MB")

        return Panel(
            table,
            title=bold("NETWORK"),
            border_style="green",
            box=box.ASCII
        )


class MempoolCard(Static):
    """Mempool statistics"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None
        self.data = {}

    def set_rpc(self, rpc: BitcoinRPC):
        self.rpc = rpc
        self.update_data()

    def update_data(self):
        if not self.rpc:
            return

        try:
            mempool_info = self.rpc.getmempoolinfo()
            self.data = {
                'size': mempool_info.get('size', 0),
                'bytes': mempool_info.get('bytes', 0),
                'usage': mempool_info.get('usage', 0) / (1024**2),
                'mempoolminfee': mempool_info.get('mempoolminfee', 0),
            }
            self.refresh()
        except:
            self.data = {}
            self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(muted("NO DATA"), title=bold("MEMPOOL"), border_style="dim", box=box.ASCII)

        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column("Key", style="dim", width=12)
        table.add_column("Value", style="white")

        tx_count = self.data.get('size', 0)
        table.add_row("TX Count", jformat(tx_count, 0))

        usage_mb = self.data.get('usage', 0)
        table.add_row("Memory", f"{usage_mb:.0f} MB")

        bytes_mb = self.data.get('bytes', 0) / (1024**2)
        table.add_row("Size", f"{bytes_mb:.0f} MB")

        min_fee = self.data.get('mempoolminfee', 0)
        table.add_row("Min Fee", f"{min_fee * 100000:.1f} s/vB")

        return Panel(
            table,
            title=bold("MEMPOOL"),
            border_style="green",
            box=box.ASCII
        )


class BlockchainCard(Static):
    """Blockchain info"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None
        self.data = {}

    def set_rpc(self, rpc: BitcoinRPC):
        self.rpc = rpc
        self.update_data()

    def update_data(self):
        if not self.rpc:
            return

        try:
            blockchain_info = self.rpc.getblockchaininfo()
            self.data = {
                'difficulty': blockchain_info.get('difficulty', 0),
                'mediantime': blockchain_info.get('mediantime', 0),
                'bestblockhash': blockchain_info.get('bestblockhash', ''),
            }
            self.refresh()
        except:
            self.data = {}
            self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel(muted("NO DATA"), title=bold("BLOCKCHAIN"), border_style="dim", box=box.ASCII)

        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column("Key", style="dim", width=12)
        table.add_column("Value", style="white")

        # Difficulty
        diff = self.data.get('difficulty', 0)
        if diff > 1e12:
            diff_str = f"{diff/1e12:.2f}T"
        elif diff > 1e9:
            diff_str = f"{diff/1e9:.2f}B"
        else:
            diff_str = f"{diff:,.0f}"
        table.add_row("Difficulty", diff_str)

        # Last block
        median_time = self.data.get('mediantime', 0)
        if median_time > 0:
            last_block_dt = datetime.fromtimestamp(median_time)
            time_ago = datetime.now() - last_block_dt
            mins_ago = int(time_ago.total_seconds() / 60)
            table.add_row("Last Block", f"{mins_ago}m ago")

        # Best block hash
        best_hash = self.data.get('bestblockhash', '')
        if best_hash:
            table.add_row("Best Block", muted(f"{best_hash[:12]}...{best_hash[-6:]}"))

        return Panel(
            table,
            title=bold("BLOCKCHAIN"),
            border_style="green",
            box=box.ASCII
        )


class ConfigCard(Static):
    """Configuration display"""

    def __init__(self, datadir: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datadir = datadir
        self.config_items = []
        self.load_config()

    def load_config(self):
        conf_path = self.datadir / 'bitcoin.conf'
        if not conf_path.exists():
            self.config_items = []
            return

        try:
            with open(conf_path, 'r') as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Hide sensitive values
                    if any(s in key.lower() for s in ['password', 'rpcauth']):
                        if 'user' not in key.lower():
                            value = muted("********")

                    self.config_items.append((key, value))
                else:
                    self.config_items.append((line, success("enabled")))

        except:
            self.config_items = []

    def render(self) -> Panel:
        if not self.config_items:
            return Panel(
                muted("bitcoin.conf not found"),
                title=bold("CONFIG"),
                border_style="dim",
                box=box.ASCII
            )

        table = Table.grid(padding=(0, 2), expand=True)
        table.add_column("Setting", style="dim", width=20)
        table.add_column("Value", style="white", no_wrap=False)

        # Show important settings first
        important = ['server', 'daemon', 'prune', 'txindex', 'rpcuser', 'rpcport', 'maxconnections']

        shown = set()
        for key in important:
            for conf_key, conf_value in self.config_items:
                if conf_key.lower() == key.lower() and conf_key not in shown:
                    table.add_row(conf_key, conf_value)
                    shown.add(conf_key)

        # Show others
        for conf_key, conf_value in self.config_items:
            if conf_key not in shown:
                table.add_row(conf_key, conf_value)

        return Panel(
            table,
            title=bold("CONFIG"),
            subtitle=muted(str(self.datadir / 'bitcoin.conf')),
            border_style="dim white",
            box=box.ASCII
        )


class BitcoinTUI(App):
    """Bitcoin Terminal - Minimalistic BBS Style"""

    CSS = """
    Screen {
        background: $surface;
    }

    BitcoinHeader {
        height: 3;
        margin: 0 0 1 0;
    }

    StatusBar {
        height: 1;
        margin: 0 1 1 1;
    }

    .cards-row {
        height: 14;
        margin: 0 1 1 1;
    }

    .config-row {
        height: auto;
        min-height: 12;
        margin: 0 1 1 1;
    }

    .card {
        width: 1fr;
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "toggle_config", "Config"),
    ]

    def __init__(self, datadir: Optional[str] = None):
        super().__init__()
        self.config = Config()
        self.datadir = Path(datadir) if datadir else self.config.get_datadir()
        self.rpc: Optional[BitcoinRPC] = None
        self.show_config = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with ScrollableContainer():
            yield BitcoinHeader()
            self.status_bar = StatusBar()
            yield self.status_bar

            # Top row: Node + Network
            with Horizontal(classes="cards-row"):
                self.node_card = NodeCard(classes="card")
                yield self.node_card

                self.network_card = NetworkCard(classes="card")
                yield self.network_card

            # Bottom row: Mempool + Blockchain
            with Horizontal(classes="cards-row"):
                self.mempool_card = MempoolCard(classes="card")
                yield self.mempool_card

                self.blockchain_card = BlockchainCard(classes="card")
                yield self.blockchain_card

            # Config (optional)
            if self.datadir:
                with Container(classes="config-row"):
                    self.config_card = ConfigCard(self.datadir)
                    yield self.config_card

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Bitcoin Terminal"
        self.sub_title = "Minimalistic Node Monitor"

        # Connect to node
        if self.datadir and self.datadir.exists():
            try:
                self.rpc = BitcoinRPC.from_datadir(self.datadir)
                self.node_card.set_rpc(self.rpc)
                self.network_card.set_rpc(self.rpc)
                self.mempool_card.set_rpc(self.rpc)
                self.blockchain_card.set_rpc(self.rpc)
            except:
                pass

        # Auto-refresh every 5 seconds
        self.set_interval(5, self.refresh_data)

    def refresh_data(self):
        if self.rpc:
            self.node_card.update_data()
            self.network_card.update_data()
            self.mempool_card.update_data()
            self.blockchain_card.update_data()

            # Update status bar
            if self.node_card.data:
                sync_pct = self.node_card.data.get('sync_pct', 0)
                if sync_pct >= 99.99:
                    self.status_bar.status = "synced"
                else:
                    self.status_bar.status = "syncing"

                self.status_bar.blocks = self.node_card.data.get('blocks', 0)

            if self.network_card.data:
                self.status_bar.peers = self.network_card.data.get('connections', 0)

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Refreshed", timeout=1)

    def action_toggle_config(self) -> None:
        if hasattr(self, 'config_card'):
            self.config_card.display = not self.config_card.display


if __name__ == "__main__":
    app = BitcoinTUI()
    app.run()
