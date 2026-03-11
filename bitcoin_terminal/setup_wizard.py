"""
First-time Setup Wizard for Bitcoin Terminal.

Interactive guided setup that:
1. Welcomes the user
2. Auto-detects Bitcoin data directories
3. Scans the local network for Bitcoin RPC nodes
4. Tests RPC connectivity (cookie → conf creds → manual entry)
5. Detects chain (mainnet/testnet/signet/regtest)
6. Saves configuration and offers to launch the dashboard
"""

import platform
import socket
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center
from textual.widgets import Static, Input, Button, Footer
from textual.screen import Screen
from textual.reactive import reactive

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

from bitcoin_terminal.config import Config
from bitcoin_terminal.rpc import BitcoinRPC

# ── Colors ────────────────────────────────────────────────────────────
BTC_ORANGE = "#F7931A"
NEON_GREEN = "#39FF14"
SOFT_GREEN = "#00E676"
SOFT_RED = "#FF5252"
SOFT_YELLOW = "#FFD740"
CYAN = "#00BCD4"
DIM = "#666666"

# ── Platform-specific default paths ───────────────────────────────────
DEFAULT_PATHS = {
    'Darwin': [
        '~/Library/Application Support/Bitcoin',
        '~/.bitcoin',
    ],
    'Linux': [
        '~/.bitcoin',
        '/mnt/bitcoin',
        '/media/bitcoin',
        '/data/bitcoin',
    ],
    'Windows': [
        '~/AppData/Roaming/Bitcoin',
        'C:/Bitcoin',
    ],
}

BITCOIN_MARKERS = ['blocks', 'chainstate', 'bitcoin.conf', 'debug.log',
                   '.lock']

CHAIN_PORTS = {
    8332: 'mainnet',
    18332: 'testnet',
    18443: 'regtest',
    38332: 'signet',
}


# ── Helpers ───────────────────────────────────────────────────────────

def _find_bitcoin_dirs() -> List[Dict[str, Any]]:
    """Quick scan for Bitcoin data directories (no recursion)."""
    results = []
    system = platform.system()
    paths = DEFAULT_PATHS.get(system, [])

    for p_str in paths:
        p = Path(p_str).expanduser()
        if p.exists() and p.is_dir():
            markers = [m for m in BITCOIN_MARKERS if (p / m).exists()]
            if len(markers) >= 2:
                has_conf = (p / 'bitcoin.conf').exists()
                has_cookie = any(
                    (p / d / '.cookie').exists()
                    for d in ['', 'signet', 'testnet3', 'testnet4', 'regtest']
                )
                results.append({
                    'path': str(p),
                    'markers': markers,
                    'has_conf': has_conf,
                    'has_cookie': has_cookie,
                })

    # Check mounted volumes (macOS/Linux)
    if system == 'Darwin':
        vol_root = Path('/Volumes')
        if vol_root.exists():
            for vol in vol_root.iterdir():
                if vol.is_dir() and vol.name not in ('.', '..', 'Macintosh HD'):
                    for sub in ['bitcoin', 'Bitcoin', '.bitcoin']:
                        candidate = vol / sub
                        if candidate.exists():
                            markers = [m for m in BITCOIN_MARKERS
                                       if (candidate / m).exists()]
                            if len(markers) >= 2:
                                results.append({
                                    'path': str(candidate),
                                    'markers': markers,
                                    'has_conf': (candidate / 'bitcoin.conf').exists(),
                                    'has_cookie': any(
                                        (candidate / d / '.cookie').exists()
                                        for d in ['', 'signet', 'testnet3',
                                                  'testnet4', 'regtest']
                                    ),
                                })
    elif system == 'Linux':
        for mount_base in ['/mnt', '/media']:
            mb = Path(mount_base)
            if mb.exists():
                try:
                    for sub in mb.iterdir():
                        if sub.is_dir():
                            for name in ['bitcoin', '.bitcoin']:
                                candidate = sub / name
                                if candidate.exists():
                                    markers = [
                                        m for m in BITCOIN_MARKERS
                                        if (candidate / m).exists()
                                    ]
                                    if len(markers) >= 2:
                                        results.append({
                                            'path': str(candidate),
                                            'markers': markers,
                                            'has_conf': (
                                                candidate / 'bitcoin.conf'
                                            ).exists(),
                                            'has_cookie': any(
                                                (candidate / d / '.cookie').exists()
                                                for d in ['', 'signet',
                                                          'testnet3',
                                                          'testnet4', 'regtest']
                                            ),
                                        })
                except PermissionError:
                    pass

    return results


def _scan_rpc_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check if an RPC port is open on a host."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except (OSError, socket.error):
        return False


def _scan_local_network_rpc(callback=None) -> List[Dict[str, Any]]:
    """Scan localhost and local network for Bitcoin RPC ports."""
    found = []
    hosts_to_check = ['127.0.0.1', 'localhost']

    # Add common local network addresses
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip not in hosts_to_check:
            hosts_to_check.append(local_ip)
    except socket.error:
        pass

    for host in hosts_to_check:
        for port, chain in CHAIN_PORTS.items():
            if _scan_rpc_port(host, port):
                found.append({
                    'host': host,
                    'port': port,
                    'chain': chain,
                })
                if callback:
                    callback(host, port, chain)

    return found


def _test_rpc_connection(host: str, port: int, user: str = '',
                         password: str = '',
                         datadir: Path = None) -> Dict[str, Any]:
    """Test RPC connection and return node info."""
    try:
        if datadir:
            env_cfg = {
                'host': host, 'port': port,
                'user': user, 'password': password,
            }
            rpc = BitcoinRPC.from_datadir(datadir, env_config=env_cfg)
        else:
            rpc = BitcoinRPC(host=host, port=port,
                             user=user, password=password)

        info = rpc.getblockchaininfo()
        net = rpc.getnetworkinfo()
        return {
            'success': True,
            'chain': info.get('chain', 'unknown'),
            'blocks': info.get('blocks', 0),
            'headers': info.get('headers', 0),
            'version': net.get('version', 0),
            'subversion': net.get('subversion', ''),
            'connections': net.get('connections', 0),
            'ibd': info.get('initialblockdownload', False),
            'auth_method': rpc.auth_method,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── Wizard Steps ──────────────────────────────────────────────────────

WIZARD_STEPS = [
    'welcome',
    'detect',
    'datadir',
    'connection',
    'test',
    'settings',
    'summary',
]


class SetupWizard(Screen):
    """Full-screen first-time setup wizard."""

    BINDINGS = [
        ("escape", "quit_wizard", "Quit"),
    ]

    CSS = """
    SetupWizard {
        background: #0a0a0a;
    }
    #wizard-header {
        height: 3;
        content-align: center middle;
        background: #111111;
        margin: 0 2;
    }
    #wizard-body {
        height: 1fr;
        margin: 1 4;
        overflow-y: auto;
    }
    #wizard-footer-bar {
        height: 1;
        content-align: center middle;
        background: #111111;
        margin: 0 2;
    }
    #wizard-nav {
        height: 3;
        align: center middle;
        margin: 0 4;
    }
    #wizard-nav Button {
        margin: 0 1;
        min-width: 16;
    }
    .wizard-input {
        margin: 1 2;
        width: 60;
    }
    #step-progress {
        height: 1;
        content-align: center middle;
        background: #0d0d0d;
        margin: 0 2;
    }
    """

    step = reactive(0)

    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self._found_dirs: List[Dict] = []
        self._found_rpc: List[Dict] = []
        self._selected_dir: Optional[str] = None
        self._rpc_host = '127.0.0.1'
        self._rpc_port = 8332
        self._rpc_user = ''
        self._rpc_password = ''
        self._test_result: Dict = {}
        self._refresh_interval = 5
        self._scanning = False
        self._scan_status = ''

    def compose(self) -> ComposeResult:
        yield Static(id="wizard-header")
        yield Static(id="step-progress")
        yield Vertical(
            Static(id="wizard-content"),
            Input(placeholder="", id="wizard-input",
                  classes="wizard-input"),
            id="wizard-body",
        )
        with Center(id="wizard-nav"):
            yield Button("Back", id="btn-back", variant="default")
            yield Button("Next", id="btn-next", variant="primary")
            yield Button("Skip", id="btn-skip", variant="default")
        yield Static(id="wizard-footer-bar")

    def on_mount(self) -> None:
        self._render_step()

    def watch_step(self, value: int) -> None:
        self._render_step()

    def _render_step(self) -> None:
        """Render the current step."""
        step_name = WIZARD_STEPS[self.step] if self.step < len(WIZARD_STEPS) else 'summary'

        # Header
        header = self.query_one("#wizard-header", Static)
        ht = Text()
        ht.append("\n ₿ ", style=f"bold {BTC_ORANGE}")
        ht.append("BITCOIN TERMINAL SETUP", style=f"bold {BTC_ORANGE}")
        header.update(ht)

        # Progress bar
        progress = self.query_one("#step-progress", Static)
        pt = Text()
        pt.append("  ")
        for i, sname in enumerate(WIZARD_STEPS):
            if i == self.step:
                pt.append(f" {sname.upper()} ",
                          style=f"bold on {BTC_ORANGE} #000000")
            elif i < self.step:
                pt.append(f" {sname} ", style=f"bold {NEON_GREEN}")
            else:
                pt.append(f" {sname} ", style="dim")
            if i < len(WIZARD_STEPS) - 1:
                pt.append(" › ", style="dim")
        progress.update(pt)

        # Nav buttons
        btn_back = self.query_one("#btn-back", Button)
        btn_next = self.query_one("#btn-next", Button)
        btn_skip = self.query_one("#btn-skip", Button)

        btn_back.display = self.step > 0
        btn_skip.display = step_name in ('detect', 'settings')

        if step_name == 'summary':
            btn_next.label = "Launch Dashboard ₿"
            btn_next.variant = "success"
        elif step_name == 'test':
            btn_next.label = "Test Connection"
            btn_next.variant = "warning"
        elif step_name == 'detect':
            btn_next.label = "Scan Now"
            btn_next.variant = "warning"
        else:
            btn_next.label = "Next →"
            btn_next.variant = "primary"

        # Content
        content = self.query_one("#wizard-content", Static)
        renderer = getattr(self, f'_render_{step_name}', None)
        if renderer:
            content.update(renderer())

        # Footer
        footer = self.query_one("#wizard-footer-bar", Static)
        ft = Text()
        ft.append(f"  Step {self.step + 1}/{len(WIZARD_STEPS)}", style="dim")
        ft.append("  •  ", style="dim")
        ft.append("Esc", style=f"bold {BTC_ORANGE}")
        ft.append(" quit  ", style="dim")
        footer.update(ft)

        # Input widget visibility per step
        inp = self.query_one("#wizard-input", Input)
        if step_name == 'datadir':
            inp.display = True
            inp.placeholder = "/path/to/bitcoin/datadir"
            inp.value = ""
        elif step_name == 'connection':
            inp.display = True
            inp.placeholder = "user:password@host:port  or  host:port"
            inp.value = ""
        elif step_name == 'settings':
            inp.display = True
            inp.placeholder = "Refresh interval in seconds (3-30)"
            inp.value = ""
        else:
            inp.display = False

    # ── Step renderers ────────────────────────────────────────────────

    def _render_welcome(self) -> Text:
        t = Text()
        t.append("\n\n")
        t.append("    ██████╗ ██╗████████╗ ██████╗ ██████╗ ██╗███╗   ██╗\n",
                 style=BTC_ORANGE)
        t.append("    ██╔══██╗██║╚══██╔══╝██╔════╝██╔═══██╗██║████╗  ██║\n",
                 style=BTC_ORANGE)
        t.append("    ██████╔╝██║   ██║   ██║     ██║   ██║██║██╔██╗ ██║\n",
                 style=BTC_ORANGE)
        t.append("    ██╔══██╗██║   ██║   ██║     ██║   ██║██║██║╚██╗██║\n",
                 style=BTC_ORANGE)
        t.append("    ██████╔╝██║   ██║   ╚██████╗╚██████╔╝██║██║ ╚████║\n",
                 style=BTC_ORANGE)
        t.append("    ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝\n",
                 style=BTC_ORANGE)
        t.append("           T E R M I N A L\n\n", style=f"bold {NEON_GREEN}")

        t.append("    Welcome to Bitcoin Terminal!\n\n",
                 style=f"bold {BTC_ORANGE}")
        t.append("    This wizard will help you set up your node monitor.\n",
                 style="white")
        t.append("    We'll walk through a few quick steps:\n\n",
                 style="dim")

        steps = [
            ("1.", "Detect", "Find your Bitcoin data directory"),
            ("2.", "Connect", "Set up RPC connection to your node"),
            ("3.", "Test", "Verify everything works"),
            ("4.", "Configure", "Set your display preferences"),
        ]
        for num, label, desc in steps:
            t.append(f"      {num} ", style=f"bold {BTC_ORANGE}")
            t.append(f"{label:12s}", style=f"bold {NEON_GREEN}")
            t.append(f"{desc}\n", style="white")

        t.append("\n    Most settings are auto-detected. You'll only need\n",
                 style="dim")
        t.append("    to answer questions when we can't figure it out.\n\n",
                 style="dim")

        t.append("    Press ", style="dim")
        t.append("Next →", style=f"bold {BTC_ORANGE}")
        t.append(" to begin.\n", style="dim")
        return t

    def _render_detect(self) -> Text:
        t = Text()
        t.append("\n  🔍 NODE DETECTION\n\n",
                 style=f"bold {BTC_ORANGE}")
        t.append("  We'll scan your system for Bitcoin data directories\n",
                 style="white")
        t.append("  and check for running Bitcoin nodes on the network.\n\n",
                 style="dim")

        if self._scanning:
            t.append(f"  ⏳ {self._scan_status}\n", style=f"bold {SOFT_YELLOW}")
            return t

        if self._found_dirs:
            t.append(f"  ✓ Found {len(self._found_dirs)} Bitcoin "
                     f"director{'y' if len(self._found_dirs) == 1 else 'ies'}:\n\n",
                     style=f"bold {NEON_GREEN}")
            for i, d in enumerate(self._found_dirs):
                marker = "▸" if d['path'] == self._selected_dir else " "
                t.append(f"    {marker} ", style=f"bold {BTC_ORANGE}")
                t.append(f"{d['path']}\n", style="white")
                detail_parts = []
                if d.get('has_conf'):
                    detail_parts.append("bitcoin.conf ✓")
                if d.get('has_cookie'):
                    detail_parts.append(".cookie ✓")
                detail_parts.append(
                    f"{len(d['markers'])} markers")
                t.append(f"      {' • '.join(detail_parts)}\n",
                         style="dim")
            t.append("\n")
        elif self._found_dirs is not None and not self._scanning:
            t.append("  Press ", style="dim")
            t.append("Scan Now", style=f"bold {BTC_ORANGE}")
            t.append(" to search for Bitcoin directories.\n\n", style="dim")

        if self._found_rpc:
            t.append(f"  ✓ Found {len(self._found_rpc)} RPC "
                     f"endpoint{'s' if len(self._found_rpc) != 1 else ''}:\n\n",
                     style=f"bold {NEON_GREEN}")
            for r in self._found_rpc:
                t.append(f"    • {r['host']}:{r['port']}",
                         style="white")
                t.append(f"  ({r['chain']})\n",
                         style=f"bold {CYAN}")
            t.append("\n")

        if not self._found_dirs and not self._found_rpc and not self._scanning:
            t.append("  Scanning will check:\n", style="dim")
            t.append("    • Default Bitcoin Core paths for your OS\n",
                     style="dim")
            t.append("    • Mounted external volumes\n", style="dim")
            t.append("    • Local network RPC ports "
                     "(8332, 18332, 18443, 38332)\n\n",
                     style="dim")

        return t

    def _render_datadir(self) -> Text:
        t = Text()
        t.append("\n  📁 DATA DIRECTORY\n\n",
                 style=f"bold {BTC_ORANGE}")

        if self._selected_dir:
            p = Path(self._selected_dir)
            t.append("  Selected directory:\n", style="dim")
            t.append(f"  {self._selected_dir}\n\n",
                     style=f"bold {NEON_GREEN}")

            # Show what we found in it
            if p.exists():
                contents = []
                for marker in BITCOIN_MARKERS:
                    if (p / marker).exists():
                        contents.append(marker)
                t.append("  Contents found: ", style="dim")
                t.append(", ".join(contents), style="white")
                t.append("\n\n")

                # Check for chain subdirs
                chains_found = []
                for chain_dir in ['', 'signet', 'testnet3', 'testnet4',
                                  'regtest']:
                    sub = p / chain_dir if chain_dir else p
                    if (sub / '.cookie').exists():
                        chain_label = chain_dir if chain_dir else 'mainnet'
                        chains_found.append(chain_label)
                if chains_found:
                    t.append("  Active chains: ", style="dim")
                    t.append(", ".join(chains_found),
                             style=f"bold {CYAN}")
                    t.append("\n\n")

                # Estimate size
                try:
                    blocks_dir = p / 'blocks'
                    if blocks_dir.exists():
                        size = sum(
                            f.stat().st_size
                            for f in blocks_dir.iterdir()
                            if f.is_file()
                        )
                        t.append("  Blocks dir size: ", style="dim")
                        t.append(f"~{size / (1024**3):.1f} GB\n\n",
                                 style="white")
                except (OSError, PermissionError):
                    pass
        else:
            t.append("  No directory detected automatically.\n\n",
                     style=SOFT_YELLOW)

        t.append("  To change, type a path below and press Enter:\n\n",
                 style="dim")

        return t

    def _render_connection(self) -> Text:
        t = Text()
        t.append("\n  🔗 RPC CONNECTION\n\n",
                 style=f"bold {BTC_ORANGE}")
        t.append("  Configure how to connect to your Bitcoin node.\n\n",
                 style="white")

        # Show current settings
        t.append("  Current settings:\n\n", style="dim")
        t.append("    Host:     ", style="dim")
        t.append(f"{self._rpc_host}\n", style="white")
        t.append("    Port:     ", style="dim")
        t.append(f"{self._rpc_port}\n", style="white")

        # Auth method detection
        if self._selected_dir:
            p = Path(self._selected_dir)
            # Check cookie
            cookie_found = False
            for chain_dir in ['', 'signet', 'testnet3', 'testnet4',
                              'regtest']:
                sub = p / chain_dir if chain_dir else p
                if (sub / '.cookie').exists():
                    cookie_found = True
                    break

            if cookie_found:
                t.append("    Auth:     ", style="dim")
                t.append(".cookie file detected ✓\n",
                         style=f"bold {NEON_GREEN}")
                t.append("\n  Cookie auth will be used automatically.\n",
                         style=SOFT_GREEN)
                t.append("  No username/password needed!\n\n",
                         style="dim")
            else:
                # Check bitcoin.conf for rpcuser/rpcpassword
                conf_path = p / 'bitcoin.conf'
                has_conf_auth = False
                if conf_path.exists():
                    try:
                        conf_text = conf_path.read_text()
                        if 'rpcuser' in conf_text or 'rpcauth' in conf_text:
                            has_conf_auth = True
                    except OSError:
                        pass

                if has_conf_auth:
                    t.append("    Auth:     ", style="dim")
                    t.append("bitcoin.conf credentials detected ✓\n",
                             style=f"bold {NEON_GREEN}")
                    t.append("\n  Credentials from bitcoin.conf will be used.\n\n",
                             style="dim")
                else:
                    t.append("    Auth:     ", style="dim")
                    t.append("No auto-auth found\n",
                             style=f"bold {SOFT_YELLOW}")
                    t.append("\n  You'll need to enter RPC credentials.\n",
                             style=SOFT_YELLOW)
                    t.append("  (Check your bitcoin.conf for rpcuser/rpcpassword)\n\n",
                             style="dim")

        if self._rpc_user:
            t.append("    User:     ", style="dim")
            t.append(f"{self._rpc_user}\n", style="white")
            t.append("    Password: ", style="dim")
            t.append("•" * min(len(self._rpc_password), 12) + "\n",
                     style="dim")

        t.append("\n  To change host/port/credentials, type below:\n",
                 style="dim")
        t.append("  Format: ", style="dim")
        t.append("host:port", style=f"bold {CYAN}")
        t.append("  or  ", style="dim")
        t.append("user:password@host:port\n\n", style=f"bold {CYAN}")

        return t

    def _render_test(self) -> Text:
        t = Text()
        t.append("\n  🧪 CONNECTION TEST\n\n",
                 style=f"bold {BTC_ORANGE}")

        if not self._test_result:
            t.append("  Ready to test RPC connection.\n\n", style="white")
            t.append("  Will connect to: ", style="dim")
            t.append(f"{self._rpc_host}:{self._rpc_port}\n",
                     style=f"bold {CYAN}")
            if self._selected_dir:
                t.append("  Data directory: ", style="dim")
                t.append(f"{self._selected_dir}\n", style="white")
            t.append("\n  Press ", style="dim")
            t.append("Test Connection", style=f"bold {BTC_ORANGE}")
            t.append(" to verify.\n", style="dim")
        elif self._test_result.get('success'):
            r = self._test_result
            t.append("  ✓ CONNECTION SUCCESSFUL!\n\n",
                     style=f"bold {NEON_GREEN}")

            # Node info table
            t.append("    Node:        ", style="dim")
            t.append(f"{r.get('subversion', '?')}\n",
                     style=f"bold {NEON_GREEN}")
            t.append("    Chain:       ", style="dim")
            chain = r.get('chain', 'unknown')
            chain_color = NEON_GREEN if chain == 'main' else SOFT_YELLOW
            t.append(f"{chain}\n", style=f"bold {chain_color}")
            t.append("    Blocks:      ", style="dim")
            t.append(f"{r.get('blocks', 0):,}\n", style="white")
            t.append("    Headers:     ", style="dim")
            t.append(f"{r.get('headers', 0):,}\n", style="white")
            t.append("    Connections: ", style="dim")
            t.append(f"{r.get('connections', 0)}\n", style="white")
            t.append("    Auth method: ", style="dim")
            t.append(f"{r.get('auth_method', '?')}\n",
                     style=f"bold {CYAN}")

            if r.get('ibd'):
                t.append("\n  ⚠ Node is in Initial Block Download (syncing)\n",
                         style=f"bold {SOFT_YELLOW}")
                pct = 0
                headers = r.get('headers', 0)
                if headers > 0:
                    pct = r.get('blocks', 0) / headers * 100
                t.append(f"    Sync progress: {pct:.1f}%\n",
                         style=SOFT_YELLOW)
            t.append("\n  Press ", style="dim")
            t.append("Next →", style=f"bold {BTC_ORANGE}")
            t.append(" to continue.\n", style="dim")
        else:
            err = self._test_result.get('error', 'Unknown error')
            t.append("  ✗ CONNECTION FAILED\n\n",
                     style=f"bold {SOFT_RED}")
            t.append(f"  Error: {err}\n\n", style=SOFT_RED)

            # Troubleshooting tips
            t.append("  Troubleshooting:\n\n", style=f"bold {SOFT_YELLOW}")
            if 'auth' in err.lower() or '401' in err:
                t.append("    • Check rpcuser/rpcpassword in bitcoin.conf\n",
                         style="white")
                t.append("    • Make sure the node has been restarted after"
                         " config changes\n", style="white")
                t.append("    • Try deleting .cookie and restarting"
                         " the node\n", style="white")
            elif 'connect' in err.lower() or 'refused' in err.lower():
                t.append("    • Is Bitcoin Core running?\n", style="white")
                t.append("    • Check that server=1 is in bitcoin.conf\n",
                         style="white")
                t.append("    • Verify the host and port are correct\n",
                         style="white")
                t.append("    • Check rpcallowip if connecting remotely\n",
                         style="white")
            else:
                t.append("    • Ensure Bitcoin Core is running\n",
                         style="white")
                t.append("    • Check bitcoin.conf for server=1\n",
                         style="white")
                t.append("    • Verify RPC credentials\n", style="white")

            t.append("\n  Press ", style="dim")
            t.append("Back", style=f"bold {BTC_ORANGE}")
            t.append(" to adjust settings, or ", style="dim")
            t.append("Test Connection", style=f"bold {BTC_ORANGE}")
            t.append(" to retry.\n", style="dim")
        return t

    def _render_settings(self) -> Text:
        t = Text()
        t.append("\n  ⚙ DISPLAY SETTINGS\n\n",
                 style=f"bold {BTC_ORANGE}")
        t.append("  Configure how the dashboard behaves.\n\n",
                 style="white")

        t.append("  Refresh interval: ", style="dim")
        t.append(f"{self._refresh_interval} seconds\n",
                 style=f"bold {NEON_GREEN}")
        t.append("  (How often the dashboard fetches new data)\n\n",
                 style="dim")

        t.append("  Recommended:\n", style="dim")
        t.append("    • ", style="dim")
        t.append("3s", style=f"bold {NEON_GREEN}")
        t.append("  — Fast updates, higher CPU usage\n", style="dim")
        t.append("    • ", style="dim")
        t.append("5s", style=f"bold {NEON_GREEN}")
        t.append("  — Balanced (default)\n", style="dim")
        t.append("    • ", style="dim")
        t.append("10s", style=f"bold {NEON_GREEN}")
        t.append("  — Slower updates, minimal resources\n\n", style="dim")

        t.append("  Type a number (3-30) below to change,\n", style="dim")
        t.append("  or press Next to keep the default.\n\n", style="dim")

        return t

    def _render_summary(self) -> Text:
        t = Text()
        t.append("\n  ✓ SETUP COMPLETE\n\n",
                 style=f"bold {NEON_GREEN}")
        t.append("  Your configuration:\n\n", style="white")

        # Data directory
        t.append("    Data directory:  ", style="dim")
        if self._selected_dir:
            t.append(f"{self._selected_dir}\n",
                     style=f"bold {NEON_GREEN}")
        else:
            t.append("Not set\n", style=SOFT_YELLOW)

        # RPC
        t.append("    RPC endpoint:    ", style="dim")
        t.append(f"{self._rpc_host}:{self._rpc_port}\n",
                 style=f"bold {CYAN}")

        # Auth
        t.append("    Auth method:     ", style="dim")
        if self._test_result.get('success'):
            t.append(f"{self._test_result.get('auth_method', 'auto')}\n",
                     style=f"bold {NEON_GREEN}")
        elif self._rpc_user:
            t.append("password\n", style="white")
        else:
            t.append("auto-detect (cookie)\n", style="white")

        # Node info from test
        if self._test_result.get('success'):
            r = self._test_result
            t.append("    Node:            ", style="dim")
            t.append(f"{r.get('subversion', '?')}\n",
                     style=f"bold {NEON_GREEN}")
            t.append("    Chain:           ", style="dim")
            t.append(f"{r.get('chain', '?')}\n",
                     style=f"bold {CYAN}")
            t.append("    Block height:    ", style="dim")
            t.append(f"{r.get('blocks', 0):,}\n", style="white")

        # Refresh
        t.append("    Refresh:         ", style="dim")
        t.append(f"{self._refresh_interval}s\n",
                 style=f"bold {NEON_GREEN}")

        t.append("\n  All settings saved to ", style="dim")
        t.append(".env", style=f"bold {CYAN}")
        t.append(" file.\n", style="dim")
        t.append("  You can re-run this wizard with ",
                 style="dim")
        t.append("--force-scan\n\n", style=f"bold {CYAN}")

        t.append("  Press ", style="dim")
        t.append("Launch Dashboard ₿", style=f"bold {NEON_GREEN}")
        t.append(" to start monitoring!\n", style="dim")

        return t

    # ── Event handlers ────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        step_name = WIZARD_STEPS[self.step]

        if btn_id == "btn-back":
            if self.step > 0:
                self.step -= 1

        elif btn_id == "btn-skip":
            if step_name == 'detect':
                # Skip detection, go to datadir
                self.step += 1
            elif step_name == 'settings':
                self.step += 1

        elif btn_id == "btn-next":
            self._handle_next(step_name)

    def _handle_next(self, step_name: str) -> None:
        if step_name == 'welcome':
            self.step += 1

        elif step_name == 'detect':
            if self._found_dirs or self._found_rpc:
                # Already scanned, proceed
                self._auto_select_best()
                self.step += 1
            else:
                self._run_scan()

        elif step_name == 'datadir':
            self.step += 1

        elif step_name == 'connection':
            self._test_result = {}  # Reset test
            self.step += 1

        elif step_name == 'test':
            if self._test_result.get('success'):
                self.step += 1
            else:
                self._run_test()

        elif step_name == 'settings':
            self.step += 1

        elif step_name == 'summary':
            self._save_and_launch()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submissions on various steps."""
        value = event.value.strip()
        if not value:
            return

        step_name = WIZARD_STEPS[self.step]

        if step_name == 'datadir':
            p = Path(value).expanduser()
            if p.exists() and p.is_dir():
                self._selected_dir = str(p)
                self._render_step()
                self.notify(f"Directory set: {p}", timeout=2)
            else:
                self.notify(f"Directory not found: {p}",
                            severity="error", timeout=3)

        elif step_name == 'connection':
            self._parse_connection_input(value)
            self._render_step()

        elif step_name == 'settings':
            try:
                val = int(value)
                if 3 <= val <= 30:
                    self._refresh_interval = val
                    self._render_step()
                    self.notify(f"Refresh interval: {val}s", timeout=2)
                else:
                    self.notify("Please enter a number between 3 and 30",
                                severity="warning", timeout=3)
            except ValueError:
                self.notify("Please enter a valid number",
                            severity="warning", timeout=3)

    def _parse_connection_input(self, value: str) -> None:
        """Parse connection string: user:pass@host:port or host:port."""
        if '@' in value:
            auth_part, host_part = value.rsplit('@', 1)
            if ':' in auth_part:
                self._rpc_user, self._rpc_password = (
                    auth_part.split(':', 1))
            else:
                self._rpc_user = auth_part
        else:
            host_part = value

        if ':' in host_part:
            h, p = host_part.rsplit(':', 1)
            self._rpc_host = h or self._rpc_host
            try:
                self._rpc_port = int(p)
            except ValueError:
                pass
        else:
            self._rpc_host = host_part

    def _auto_select_best(self) -> None:
        """Auto-select the best detected directory."""
        if not self._selected_dir and self._found_dirs:
            # Prefer directory with most markers
            best = max(self._found_dirs, key=lambda d: len(d['markers']))
            self._selected_dir = best['path']

        # Auto-fill RPC from scan
        if self._found_rpc:
            best_rpc = self._found_rpc[0]
            self._rpc_host = best_rpc['host']
            self._rpc_port = best_rpc['port']

    def _run_scan(self) -> None:
        """Run directory + network scan in background."""
        self._scanning = True
        self._scan_status = "Scanning for Bitcoin directories..."
        self._render_step()

        def _do_scan():
            self._found_dirs = _find_bitcoin_dirs()
            self._scan_status = "Scanning network for RPC ports..."
            self.call_from_thread(self._render_step)
            self._found_rpc = _scan_local_network_rpc()
            self._scanning = False
            self._auto_select_best()
            self.call_from_thread(self._render_step)

        thread = threading.Thread(target=_do_scan, daemon=True)
        thread.start()

    def _run_test(self) -> None:
        """Test the RPC connection."""
        self._test_result = {}
        self._render_step()

        datadir = Path(self._selected_dir) if self._selected_dir else None

        def _do_test():
            result = _test_rpc_connection(
                host=self._rpc_host,
                port=self._rpc_port,
                user=self._rpc_user,
                password=self._rpc_password,
                datadir=datadir,
            )
            self._test_result = result

            # If successful, detect port-based chain info
            if result.get('success'):
                chain = result.get('chain', '')
                if chain == 'main':
                    self._rpc_port = self._rpc_port or 8332
                elif chain == 'test':
                    self._rpc_port = self._rpc_port or 18332
                elif chain == 'signet':
                    self._rpc_port = self._rpc_port or 38332
                elif chain == 'regtest':
                    self._rpc_port = self._rpc_port or 18443

                # Auto-advance to next step on success
                self.call_from_thread(self._advance_after_test)
            else:
                self.call_from_thread(self._render_step)

        thread = threading.Thread(target=_do_test, daemon=True)
        thread.start()

    def _advance_after_test(self) -> None:
        """Render the test success, then user clicks Next."""
        self._render_step()
        # Change button to "Next" now that test succeeded
        btn_next = self.query_one("#btn-next", Button)
        btn_next.label = "Next →"
        btn_next.variant = "primary"

    def _save_and_launch(self) -> None:
        """Save all settings and dismiss wizard."""
        # Save data directory
        if self._selected_dir:
            self.config.set_datadir(Path(self._selected_dir))

        # Save RPC config
        self.config.set_rpc_config(
            host=self._rpc_host,
            port=self._rpc_port,
            user=self._rpc_user,
            password=self._rpc_password,
        )

        # Save display config
        self.config.set_display_config(
            refresh_interval=self._refresh_interval,
        )

        # Dismiss wizard — the app will detect the saved config
        self.dismiss(True)

    def action_quit_wizard(self) -> None:
        self.dismiss(False)
