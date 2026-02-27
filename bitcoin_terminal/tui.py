"""
Main TUI Application
Beautiful terminal interface for Bitcoin Node monitoring
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, Label
from textual.reactive import reactive
from textual import events
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
import pyfiglet
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bitcoin_terminal.config import Config
from bitcoin_terminal.rpc import BitcoinRPC
from bitcoin_terminal.scanner import BitcoinScanner


class BitcoinBanner(Static):
    """Display Bitcoin banner"""

    def on_mount(self) -> None:
        title = pyfiglet.figlet_format("BITCOIN", font="slant")
        subtitle = "Terminal - Node Monitor"

        banner = Text()
        banner.append(title, style="bold orange1")
        banner.append("\n")
        banner.append(subtitle, style="bold white")

        self.update(Panel(
            banner,
            border_style="orange1",
            box=box.HEAVY
        ))


class NodeStatus(Static):
    """Display node connection status"""

    status = reactive("disconnected")
    block_height = reactive(0)
    peers = reactive(0)
    sync_progress = reactive(0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None

    def set_rpc(self, rpc: BitcoinRPC):
        """Set RPC client"""
        self.rpc = rpc
        self.update_status()

    def update_status(self):
        """Update node status information"""
        if not self.rpc:
            self.status = "disconnected"
            return

        try:
            if self.rpc.test_connection():
                self.status = "connected"

                # Get blockchain info
                blockchain_info = self.rpc.getblockchaininfo()
                self.block_height = blockchain_info.get('blocks', 0)
                self.sync_progress = blockchain_info.get('verificationprogress', 0.0) * 100

                # Get peer count
                network_info = self.rpc.getnetworkinfo()
                self.peers = network_info.get('connections', 0)
            else:
                self.status = "disconnected"
        except:
            self.status = "error"

    def render(self) -> Panel:
        """Render the node status panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        # Status indicator
        if self.status == "connected":
            status_text = "[green]● ONLINE[/green]"
        elif self.status == "error":
            status_text = "[red]● ERROR[/red]"
        else:
            status_text = "[yellow]● OFFLINE[/yellow]"

        table.add_row("Status", status_text)
        table.add_row("Block Height", f"{self.block_height:,}")
        table.add_row("Sync Progress", f"{self.sync_progress:.2f}%")
        table.add_row("Peers", str(self.peers))

        return Panel(
            table,
            title="[bold]⚡ Node Status[/bold]",
            border_style="blue",
            box=box.ROUNDED
        )


class BlockchainInfo(Static):
    """Display blockchain information"""

    chain = reactive("unknown")
    difficulty = reactive(0.0)
    size_on_disk = reactive(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None

    def set_rpc(self, rpc: BitcoinRPC):
        """Set RPC client"""
        self.rpc = rpc
        self.update_info()

    def update_info(self):
        """Update blockchain information"""
        if not self.rpc:
            return

        try:
            blockchain_info = self.rpc.getblockchaininfo()
            self.chain = blockchain_info.get('chain', 'unknown')
            self.difficulty = blockchain_info.get('difficulty', 0.0)
            self.size_on_disk = blockchain_info.get('size_on_disk', 0)
        except:
            pass

    def render(self) -> Panel:
        """Render the blockchain info panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        # Format size
        size_gb = self.size_on_disk / (1024**3)

        table.add_row("Network", self.chain.upper())
        table.add_row("Difficulty", f"{self.difficulty:,.0f}")
        table.add_row("Size on Disk", f"{size_gb:.2f} GB")
        table.add_row("Last Update", datetime.now().strftime("%H:%M:%S"))

        return Panel(
            table,
            title="[bold]⛓️  Blockchain[/bold]",
            border_style="green",
            box=box.ROUNDED
        )


class MempoolInfo(Static):
    """Display mempool information"""

    tx_count = reactive(0)
    mempool_size = reactive(0)
    mempool_bytes = reactive(0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc: Optional[BitcoinRPC] = None

    def set_rpc(self, rpc: BitcoinRPC):
        """Set RPC client"""
        self.rpc = rpc
        self.update_info()

    def update_info(self):
        """Update mempool information"""
        if not self.rpc:
            return

        try:
            mempool_info = self.rpc.getmempoolinfo()
            self.tx_count = mempool_info.get('size', 0)
            self.mempool_size = mempool_info.get('bytes', 0)
            self.mempool_bytes = mempool_info.get('usage', 0)
        except:
            pass

    def render(self) -> Panel:
        """Render the mempool info panel"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        size_mb = self.mempool_bytes / (1024**2)

        table.add_row("Transactions", f"{self.tx_count:,}")
        table.add_row("Size", f"{size_mb:.2f} MB")
        table.add_row("Bytes", f"{self.mempool_size:,}")

        return Panel(
            table,
            title="[bold]💾 Mempool[/bold]",
            border_style="yellow",
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
        margin: 1;
    }

    .info-panel {
        height: 12;
        margin: 1;
    }

    .controls {
        height: 5;
        margin: 1;
        align: center middle;
    }

    Button {
        margin: 0 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("s", "scan", "Scan for Bitcoin dirs"),
    ]

    def __init__(self, datadir: Optional[str] = None):
        super().__init__()
        self.config = Config()
        self.datadir = Path(datadir) if datadir else self.config.get_datadir()
        self.rpc: Optional[BitcoinRPC] = None

    def compose(self) -> ComposeResult:
        """Compose the UI"""
        yield Header(show_clock=True)

        yield BitcoinBanner()

        with Horizontal():
            with Container(classes="info-panel"):
                self.node_status = NodeStatus()
                yield self.node_status

            with Container(classes="info-panel"):
                self.blockchain_info = BlockchainInfo()
                yield self.blockchain_info

            with Container(classes="info-panel"):
                self.mempool_info = MempoolInfo()
                yield self.mempool_info

        with Container(classes="controls"):
            yield Button("🔄 Refresh", id="refresh", variant="primary")
            yield Button("🔍 Scan", id="scan", variant="default")
            yield Button("⚙️  Settings", id="settings", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted"""
        self.title = "Bitcoin Terminal"
        self.sub_title = "Node Monitor"

        # Try to connect to node
        if self.datadir and self.datadir.exists():
            try:
                self.rpc = BitcoinRPC.from_datadir(self.datadir)
                self.node_status.set_rpc(self.rpc)
                self.blockchain_info.set_rpc(self.rpc)
                self.mempool_info.set_rpc(self.rpc)
            except:
                pass

        # Set up auto-refresh
        self.set_interval(5, self.refresh_data)

    def refresh_data(self):
        """Refresh all data"""
        if self.rpc:
            self.node_status.update_status()
            self.blockchain_info.update_info()
            self.mempool_info.update_info()

    def action_refresh(self) -> None:
        """Refresh data manually"""
        self.refresh_data()

    def action_scan(self) -> None:
        """Scan for Bitcoin directories"""
        self.exit()
        scanner = BitcoinScanner()
        results = scanner.scan()

        if results:
            # Update config with first found directory
            self.config.set_datadir(Path(results[0]['path']))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh":
            self.action_refresh()
        elif event.button.id == "scan":
            self.action_scan()
        elif event.button.id == "settings":
            pass  # TODO: Implement settings dialog


if __name__ == "__main__":
    app = BitcoinTUI()
    app.run()
