"""
Main TUI Application
Beautiful terminal interface for Bitcoin Node monitoring
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
import pyfiglet
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import re

from bitcoin_terminal.config import Config
from bitcoin_terminal.rpc import BitcoinRPC


class BitcoinBanner(Static):
    """Display Bitcoin banner"""

    def on_mount(self) -> None:
        title = pyfiglet.figlet_format("BITCOIN", font="slant")
        subtitle = "Node Monitor v0.1.0"

        banner_text = Text()
        banner_text.append(title, style="bold orange1")
        banner_text.append("\n")
        banner_text.append(subtitle, style="bold white")

        self.update(Panel(
            banner_text,
            border_style="orange1",
            box=box.HEAVY
        ))


class NodeHealthCard(Static):
    """Display node health and sync status"""

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
                'verification_progress': blockchain_info.get('verificationprogress', 0.0) * 100,
                'ibd': blockchain_info.get('initialblockdownload', False),
                'size_on_disk': blockchain_info.get('size_on_disk', 0) / (1024**3),  # GB
                'pruned': blockchain_info.get('pruned', False),
                'connections': network_info.get('connections', 0),
                'connections_in': network_info.get('connections_in', 0),
                'connections_out': network_info.get('connections_out', 0),
                'version': network_info.get('version', 0),
                'subversion': network_info.get('subversion', ''),
                'uptime': uptime_seconds,
            }
            self.refresh()
        except Exception as e:
            self.data = {'error': str(e)}
            self.refresh()

    def render(self) -> Panel:
        if not self.data:
            return Panel("[yellow]Connecting to node...[/yellow]", title="[bold]⚡ Node Health[/bold]", border_style="blue")

        if 'error' in self.data:
            return Panel(
                f"[red]❌ Cannot connect to Bitcoin Core[/red]\n\n"
                f"[dim]{self.data['error']}[/dim]",
                title="[bold]⚡ Node Health[/bold]",
                border_style="red"
            )

        # Create status table
        table = Table.grid(padding=(0, 2))
        table.add_column("Key", style="cyan", width=20)
        table.add_column("Value", style="white")

        # Sync status
        sync_progress = self.data.get('verification_progress', 0)
        blocks = self.data.get('blocks', 0)
        headers = self.data.get('headers', 0)
        blocks_behind = headers - blocks

        if sync_progress >= 99.99:
            sync_status = "[green]● SYNCED[/green]"
        elif self.data.get('ibd', False):
            sync_status = f"[yellow]⟳ SYNCING[/yellow] ({sync_progress:.2f}%)"
        else:
            sync_status = f"[blue]⟳ CATCHING UP[/blue] ({blocks_behind} blocks behind)"

        table.add_row("Status", sync_status)
        table.add_row("Chain", f"[bold]{self.data.get('chain', 'unknown').upper()}[/bold]")
        table.add_row("Block Height", f"[green]{blocks:,}[/green] / {headers:,}")
        table.add_row("Sync Progress", f"{sync_progress:.2f}%")

        # Uptime
        uptime = self.data.get('uptime', 0)
        uptime_str = str(timedelta(seconds=uptime)).split('.')[0]
        table.add_row("Uptime", f"[blue]{uptime_str}[/blue]")

        # Version
        version = self.data.get('version', 0)
        version_str = f"{version // 10000}.{(version // 100) % 100}.{version % 100}"
        subversion = self.data.get('subversion', '').strip('/')
        table.add_row("Version", f"{subversion or version_str}")

        # Storage
        size = self.data.get('size_on_disk', 0)
        pruned = self.data.get('pruned', False)
        storage_str = f"{size:.1f} GB"
        if pruned:
            storage_str += " [yellow](pruned)[/yellow]"
        table.add_row("Disk Usage", storage_str)

        return Panel(
            table,
            title="[bold]⚡ Node Health[/bold]",
            border_style="blue",
            box=box.ROUNDED
        )


class NetworkCard(Static):
    """Display network connections and traffic"""

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

            # Count connection types
            ipv4_count = sum(1 for p in peer_info if ':' not in p.get('addr', '').split(':')[0])
            ipv6_count = sum(1 for p in peer_info if ':' in p.get('addr', '').split(':')[0] and not p.get('addr', '').endswith('.onion'))
            tor_count = sum(1 for p in peer_info if '.onion' in p.get('addr', ''))
            i2p_count = sum(1 for p in peer_info if '.i2p' in p.get('addr', ''))

            # Calculate traffic
            total_received = sum(p.get('bytesrecv', 0) for p in peer_info) / (1024**2)  # MB
            total_sent = sum(p.get('bytessent', 0) for p in peer_info) / (1024**2)  # MB

            self.data = {
                'connections': network_info.get('connections', 0),
                'connections_in': network_info.get('connections_in', 0),
                'connections_out': network_info.get('connections_out', 0),
                'ipv4': ipv4_count,
                'ipv6': ipv6_count,
                'tor': tor_count,
                'i2p': i2p_count,
                'received_mb': total_received,
                'sent_mb': total_sent,
                'networks': network_info.get('networks', []),
                'relayfee': network_info.get('relayfee', 0),
            }
            self.refresh()
        except Exception as e:
            self.data = {'error': str(e)}
            self.refresh()

    def render(self) -> Panel:
        if not self.data or 'error' in self.data:
            return Panel("[dim]No network data[/dim]", title="[bold]🌐 Network[/bold]", border_style="green")

        table = Table.grid(padding=(0, 2))
        table.add_column("Key", style="cyan", width=20)
        table.add_column("Value", style="white")

        # Connections
        total = self.data.get('connections', 0)
        inbound = self.data.get('connections_in', 0)
        outbound = self.data.get('connections_out', 0)

        connection_str = f"[green]{total}[/green] ([blue]↓{inbound}[/blue] [yellow]↑{outbound}[/yellow])"
        table.add_row("Connections", connection_str)

        # Connection types
        conn_types = []
        if self.data.get('ipv4', 0) > 0:
            conn_types.append(f"IPv4: {self.data['ipv4']}")
        if self.data.get('ipv6', 0) > 0:
            conn_types.append(f"IPv6: {self.data['ipv6']}")
        if self.data.get('tor', 0) > 0:
            conn_types.append(f"[magenta]Tor: {self.data['tor']}[/magenta]")
        if self.data.get('i2p', 0) > 0:
            conn_types.append(f"I2P: {self.data['i2p']}")

        if conn_types:
            table.add_row("Types", " • ".join(conn_types))

        # Traffic
        received = self.data.get('received_mb', 0)
        sent = self.data.get('sent_mb', 0)
        table.add_row("Traffic ↓", f"[blue]{received:.1f} MB[/blue]")
        table.add_row("Traffic ↑", f"[yellow]{sent:.1f} MB[/yellow]")

        # Relay fee
        relay_fee = self.data.get('relayfee', 0)
        table.add_row("Min Relay Fee", f"{relay_fee * 100000:.1f} sat/vB")

        return Panel(
            table,
            title="[bold]🌐 Network[/bold]",
            border_style="green",
            box=box.ROUNDED
        )


class MempoolCard(Static):
    """Display mempool statistics"""

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
                'bytes': mempool_info.get('bytes', 0) / (1024**2),  # MB
                'usage': mempool_info.get('usage', 0) / (1024**2),  # MB
                'maxmempool': mempool_info.get('maxmempool', 0) / (1024**2),  # MB
                'mempoolminfee': mempool_info.get('mempoolminfee', 0),
                'minrelaytxfee': mempool_info.get('minrelaytxfee', 0),
                'unbroadcastcount': mempool_info.get('unbroadcastcount', 0),
            }
            self.refresh()
        except Exception as e:
            self.data = {'error': str(e)}
            self.refresh()

    def render(self) -> Panel:
        if not self.data or 'error' in self.data:
            return Panel("[dim]No mempool data[/dim]", title="[bold]💾 Mempool[/bold]", border_style="yellow")

        table = Table.grid(padding=(0, 2))
        table.add_column("Key", style="cyan", width=20)
        table.add_column("Value", style="white")

        # Transaction count
        tx_count = self.data.get('size', 0)
        table.add_row("Transactions", f"[green]{tx_count:,}[/green]")

        # Memory usage
        usage = self.data.get('usage', 0)
        max_mem = self.data.get('maxmempool', 0)
        usage_percent = (usage / max_mem * 100) if max_mem > 0 else 0
        table.add_row("Memory Usage", f"{usage:.1f} MB / {max_mem:.0f} MB ([cyan]{usage_percent:.1f}%[/cyan])")

        # Size
        size_mb = self.data.get('bytes', 0)
        table.add_row("Total Size", f"{size_mb:.1f} MB")

        # Fees
        mempool_min_fee = self.data.get('mempoolminfee', 0)
        min_relay_fee = self.data.get('minrelaytxfee', 0)
        table.add_row("Min Mempool Fee", f"[yellow]{mempool_min_fee * 100000:.1f}[/yellow] sat/vB")
        table.add_row("Min Relay Fee", f"[dim]{min_relay_fee * 100000:.1f} sat/vB[/dim]")

        # Unbroadcast
        unbroadcast = self.data.get('unbroadcastcount', 0)
        if unbroadcast > 0:
            table.add_row("Unbroadcast", f"[yellow]{unbroadcast}[/yellow]")

        return Panel(
            table,
            title="[bold]💾 Mempool[/bold]",
            border_style="yellow",
            box=box.ROUNDED
        )


class BlockchainCard(Static):
    """Display blockchain statistics"""

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
                'chain': blockchain_info.get('chain', 'unknown'),
                'blocks': blockchain_info.get('blocks', 0),
                'headers': blockchain_info.get('headers', 0),
                'bestblockhash': blockchain_info.get('bestblockhash', ''),
                'difficulty': blockchain_info.get('difficulty', 0),
                'mediantime': blockchain_info.get('mediantime', 0),
                'chainwork': blockchain_info.get('chainwork', ''),
                'pruned': blockchain_info.get('pruned', False),
                'prune_target_size': blockchain_info.get('prune_target_size', 0) / (1024**3) if blockchain_info.get('pruned') else 0,
            }
            self.refresh()
        except Exception as e:
            self.data = {'error': str(e)}
            self.refresh()

    def render(self) -> Panel:
        if not self.data or 'error' in self.data:
            return Panel("[dim]No blockchain data[/dim]", title="[bold]⛓️  Blockchain[/bold]", border_style="magenta")

        table = Table.grid(padding=(0, 2))
        table.add_column("Key", style="cyan", width=20)
        table.add_column("Value", style="white")

        # Difficulty
        difficulty = self.data.get('difficulty', 0)
        if difficulty > 1e12:
            diff_str = f"{difficulty/1e12:.2f}T"
        elif difficulty > 1e9:
            diff_str = f"{difficulty/1e9:.2f}B"
        else:
            diff_str = f"{difficulty:,.0f}"
        table.add_row("Difficulty", f"[yellow]{diff_str}[/yellow]")

        # Chain work (total hashes)
        chainwork = self.data.get('chainwork', '')
        if chainwork:
            # Convert hex to decimal and show in scientific notation
            work_int = int(chainwork, 16)
            table.add_row("Chain Work", f"[dim]2^{work_int.bit_length()}[/dim]")

        # Last block time
        median_time = self.data.get('mediantime', 0)
        if median_time > 0:
            last_block_dt = datetime.fromtimestamp(median_time)
            time_ago = datetime.now() - last_block_dt
            if time_ago.total_seconds() < 3600:
                time_str = f"{int(time_ago.total_seconds() / 60)} min ago"
            else:
                time_str = f"{int(time_ago.total_seconds() / 3600)} hours ago"
            table.add_row("Last Block", f"[green]{time_str}[/green]")

        # Best block hash (shortened)
        best_hash = self.data.get('bestblockhash', '')
        if best_hash:
            table.add_row("Best Block", f"[dim]{best_hash[:16]}...{best_hash[-8:]}[/dim]")

        # Pruning status
        if self.data.get('pruned', False):
            prune_size = self.data.get('prune_target_size', 0)
            table.add_row("Pruning", f"[yellow]Enabled ({prune_size:.0f} GB target)[/yellow]")

        return Panel(
            table,
            title="[bold]⛓️  Blockchain[/bold]",
            border_style="magenta",
            box=box.ROUNDED
        )


class ConfigCard(Static):
    """Display bitcoin.conf configuration (sanitized)"""

    def __init__(self, datadir: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datadir = datadir
        self.config_items = []
        self.load_config()

    def load_config(self):
        """Load and parse bitcoin.conf"""
        conf_path = self.datadir / 'bitcoin.conf'

        if not conf_path.exists():
            self.config_items = [("bitcoin.conf", "[yellow]Not found[/yellow]")]
            return

        try:
            with open(conf_path, 'r') as f:
                lines = f.readlines()

            # Parse config
            for line in lines:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Sanitize sensitive values
                    sensitive_keys = ['rpcpassword', 'password', 'rpcauth', 'rpcuser']
                    if any(s in key.lower() for s in sensitive_keys):
                        if 'user' in key.lower():
                            value = value  # Show username
                        else:
                            value = "[dim]********[/dim]"  # Hide password

                    self.config_items.append((key, value))
                else:
                    # Boolean flag (no value)
                    self.config_items.append((line, "[green]✓[/green]"))

        except Exception as e:
            self.config_items = [("Error", f"[red]{str(e)}[/red]")]

    def render(self) -> Panel:
        if not self.config_items:
            return Panel(
                "[yellow]No configuration found[/yellow]\n\n"
                f"[dim]Expected at: {self.datadir / 'bitcoin.conf'}[/dim]",
                title="[bold]⚙️  Configuration[/bold]",
                border_style="cyan"
            )

        # Create configuration table
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
            padding=(0, 1)
        )
        table.add_column("Setting", style="yellow", width=25)
        table.add_column("Value", style="white", no_wrap=False)

        # Add important items first, then others
        important_keys = [
            'server', 'daemon', 'prune', 'txindex', 'listen',
            'rpcuser', 'rpcport', 'rpcbind', 'rpcallowip',
            'port', 'maxconnections', 'dbcache'
        ]

        # Show important items first
        shown_keys = set()
        for key in important_keys:
            for conf_key, conf_value in self.config_items:
                if conf_key.lower() == key.lower() and conf_key not in shown_keys:
                    table.add_row(conf_key, conf_value)
                    shown_keys.add(conf_key)

        # Show remaining items
        for conf_key, conf_value in self.config_items:
            if conf_key not in shown_keys:
                table.add_row(conf_key, conf_value)

        info_text = Text()
        info_text.append("📍 ", style="dim")
        info_text.append(str(self.datadir / 'bitcoin.conf'), style="dim")

        return Panel(
            table,
            title="[bold]⚙️  Configuration[/bold]",
            subtitle=info_text,
            border_style="cyan",
            box=box.ROUNDED
        )


class BitcoinTUI(App):
    """Bitcoin Terminal TUI Application"""

    CSS = """
    Screen {
        background: $surface;
    }

    BitcoinBanner {
        height: 10;
        margin: 0 1;
    }

    .top-row {
        height: 18;
        margin: 0 1 1 1;
    }

    .middle-row {
        height: 18;
        margin: 0 1 1 1;
    }

    .config-row {
        height: auto;
        min-height: 15;
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
        ("c", "toggle_config", "Toggle Config"),
    ]

    def __init__(self, datadir: Optional[str] = None):
        super().__init__()
        self.config = Config()
        self.datadir = Path(datadir) if datadir else self.config.get_datadir()
        self.rpc: Optional[BitcoinRPC] = None
        self.show_config = True

    def compose(self) -> ComposeResult:
        """Compose the UI"""
        yield Header(show_clock=True)

        # Scrollable container for all content
        with ScrollableContainer():
            yield BitcoinBanner()

            # Top row: Node Health + Network
            with Horizontal(classes="top-row"):
                self.node_health = NodeHealthCard(classes="card")
                yield self.node_health

                self.network_card = NetworkCard(classes="card")
                yield self.network_card

            # Middle row: Mempool + Blockchain
            with Horizontal(classes="middle-row"):
                self.mempool_card = MempoolCard(classes="card")
                yield self.mempool_card

                self.blockchain_card = BlockchainCard(classes="card")
                yield self.blockchain_card

            # Config row (optional)
            if self.datadir:
                with Container(classes="config-row"):
                    self.config_card = ConfigCard(self.datadir)
                    yield self.config_card

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self.title = "Bitcoin Terminal"
        self.sub_title = f"Monitoring: {self.datadir.name if self.datadir else 'No node'}"

        # Try to connect to node
        if self.datadir and self.datadir.exists():
            try:
                self.rpc = BitcoinRPC.from_datadir(self.datadir)
                self.node_health.set_rpc(self.rpc)
                self.network_card.set_rpc(self.rpc)
                self.mempool_card.set_rpc(self.rpc)
                self.blockchain_card.set_rpc(self.rpc)
            except Exception as e:
                self.notify(f"Failed to connect to Bitcoin Core: {e}", severity="error")

        # Set up auto-refresh (every 5 seconds)
        self.set_interval(5, self.refresh_data)

    def refresh_data(self):
        """Refresh all data from Bitcoin Core"""
        if self.rpc:
            self.node_health.update_data()
            self.network_card.update_data()
            self.mempool_card.update_data()
            self.blockchain_card.update_data()

    def action_refresh(self) -> None:
        """Refresh data manually"""
        self.refresh_data()
        self.notify("Data refreshed", timeout=2)

    def action_toggle_config(self) -> None:
        """Toggle configuration display"""
        if hasattr(self, 'config_card'):
            self.config_card.display = not self.config_card.display
            self.notify(
                "Config shown" if self.config_card.display else "Config hidden",
                timeout=2
            )


if __name__ == "__main__":
    app = BitcoinTUI()
    app.run()
