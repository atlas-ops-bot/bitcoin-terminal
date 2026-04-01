"""
Bitcoin Core Node Starter
Detects if bitcoind is running and attempts to start it if not.
Tries multiple known commands/paths across platforms.
"""

import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List

from rich.console import Console
from rich.panel import Panel
from rich import box

from bitcoin_terminal.rpc import BitcoinRPC

console = Console()

# Known bitcoind binary paths per platform
_DAEMON_CANDIDATES = {
    'Darwin': [
        'bitcoind',                                                         # PATH
        '/usr/local/bin/bitcoind',                                          # Homebrew (Intel)
        '/opt/homebrew/bin/bitcoind',                                       # Homebrew (Apple Silicon)
        '/Applications/Bitcoin-Qt.app/Contents/MacOS/Bitcoin-Qt',           # GUI bundle
    ],
    'Linux': [
        'bitcoind',                                                         # PATH
        '/usr/bin/bitcoind',
        '/usr/local/bin/bitcoind',
        '/snap/bitcoin-core/current/bin/bitcoind',                          # Snap
        '/snap/bitcoin-core/current/bin/bitcoin-qt',
    ],
    'Windows': [
        'bitcoind',
        'bitcoind.exe',
        r'C:\Program Files\Bitcoin\daemon\bitcoind.exe',
        r'C:\Program Files (x86)\Bitcoin\daemon\bitcoind.exe',
        r'C:\Program Files\Bitcoin\bitcoin-qt.exe',
    ],
}

# Maximum seconds to wait for the node RPC to become reachable
_STARTUP_TIMEOUT = 30
_POLL_INTERVAL = 2


def _is_gui_binary(path: str) -> bool:
    """Check if a binary path refers to Bitcoin-Qt (GUI)."""
    lower = path.lower()
    return 'bitcoin-qt' in lower


def _find_binary() -> Optional[str]:
    """Return the first usable bitcoind / Bitcoin-Qt binary, or None."""
    system = platform.system()
    candidates = _DAEMON_CANDIDATES.get(system, _DAEMON_CANDIDATES['Linux'])

    for candidate in candidates:
        # shutil.which works for bare command names
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        # Also try the literal path for absolute entries
        if candidate.startswith(('/', 'C:\\')) and Path(candidate).is_file():
            return candidate
    return None


def _build_args(binary: str, datadir: Optional[Path] = None) -> List[str]:
    """Build the argument list for starting the daemon."""
    args = [binary]

    if _is_gui_binary(binary):
        # Bitcoin-Qt: start with -server so RPC is available
        args.append('-server')
    else:
        # bitcoind: run as background daemon
        args.append('-daemon')

    if datadir:
        args.append(f'-datadir={datadir}')

    return args


def attempt_start_node(
    datadir: Optional[Path] = None,
    env_config: Optional[dict] = None,
) -> bool:
    """Try to start Bitcoin Core if it is not already reachable.

    Returns True if the node is reachable (was already running or
    successfully started), False otherwise.
    """
    # ── 1. Test existing connection ────────────────────────────────────
    if datadir:
        rpc = BitcoinRPC.from_datadir(datadir, env_config=env_config)
    else:
        cfg = env_config or {}
        rpc = BitcoinRPC(
            host=cfg.get('host', '127.0.0.1'),
            port=cfg.get('port', 8332),
            user=cfg.get('user', ''),
            password=cfg.get('password', ''),
        )

    if rpc.test_connection():
        return True  # already running

    # ── 2. Locate a suitable binary ────────────────────────────────────
    binary = _find_binary()
    if not binary:
        console.print(Panel(
            "[yellow]Could not find bitcoind or Bitcoin-Qt.\n"
            "Please start Bitcoin Core manually.[/yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        ))
        return False

    # ── 3. Start the node ──────────────────────────────────────────────
    args = _build_args(binary, datadir)
    label = Path(binary).name

    console.print(Panel(
        f"[cyan]Bitcoin Core is not running.\n"
        f"Starting with:[/cyan] [bold]{label}[/bold]",
        border_style="cyan",
        box=box.ROUNDED,
    ))

    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        console.print(f"[red]Failed to start {label}: {exc}[/red]")
        return False

    # ── 4. Wait for RPC to become reachable ────────────────────────────
    console.print("[dim]Waiting for node to become reachable...[/dim]")
    deadline = time.monotonic() + _STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL)
        # Re-create RPC (cookie file may appear after node starts)
        if datadir:
            rpc = BitcoinRPC.from_datadir(datadir, env_config=env_config)
        if rpc.test_connection():
            console.print(f"[green]✓ Bitcoin Core ({label}) is now running.[/green]")
            return True

    console.print(
        "[yellow]Node started but RPC not yet reachable. "
        "It may still be initializing — the TUI will retry automatically.[/yellow]"
    )
    return False
