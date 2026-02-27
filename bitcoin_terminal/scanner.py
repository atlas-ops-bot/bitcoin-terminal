"""
Bitcoin Data Directory Scanner
Minimalistic BBS-style with yaspin spinners
"""

import os
import platform
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from yaspin import yaspin
from yaspin.spinners import Spinners

from bitcoin_terminal.ansi_utils import *

console = Console()


class BitcoinScanner:
    """Scans for Bitcoin Core data directories"""

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
        ]
    }

    BITCOIN_MARKERS = ['blocks', 'chainstate', 'bitcoin.conf', 'debug.log', '.lock']

    def __init__(self):
        self.system = platform.system()
        self.found_directories: List[Dict] = []

    def display_banner(self):
        """Minimalistic banner"""
        header = Text()
        header.append("[ ", style="dim")
        header.append("BITCOIN NODE SCANNER", style="bold white")
        header.append(" ]", style="dim")

        console.print(Panel(
            header,
            border_style="dim white",
            box=box.ASCII
        ))
        console.print()

    def get_search_paths(self) -> List[Path]:
        """Get list of paths to search"""
        paths = []

        # Default paths
        default_paths = self.DEFAULT_PATHS.get(self.system, [])
        for path_str in default_paths:
            expanded = Path(path_str).expanduser()
            if expanded.exists():
                paths.append(expanded)

        # Mounted volumes
        if self.system == 'Darwin':
            volumes = Path('/Volumes')
            if volumes.exists():
                for vol in volumes.iterdir():
                    if vol.is_dir() and vol.name not in ['.', '..', 'Macintosh HD']:
                        paths.append(vol)
        elif self.system == 'Linux':
            for mount_point in ['/mnt', '/media']:
                mount = Path(mount_point)
                if mount.exists():
                    for subdir in mount.iterdir():
                        if subdir.is_dir():
                            paths.append(subdir)

        return paths

    def check_bitcoin_directory(self, path: Path) -> Optional[Dict]:
        """Check if directory contains Bitcoin data"""
        try:
            markers_found = []

            for marker in self.BITCOIN_MARKERS:
                marker_path = path / marker
                if marker_path.exists():
                    markers_found.append(marker)

            # Need at least 2 markers
            if len(markers_found) >= 2:
                try:
                    size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                    size_gb = size / (1024**3)
                except:
                    size_gb = 0

                return {
                    'path': str(path),
                    'markers': markers_found,
                    'size_gb': round(size_gb, 2),
                    'has_blocks': (path / 'blocks').exists(),
                    'has_chainstate': (path / 'chainstate').exists(),
                }
        except:
            pass

        return None

    def scan_directory(self, root: Path, sp) -> None:
        """Recursively scan directory tree"""
        try:
            for item in root.iterdir():
                if item.is_dir():
                    sp.text = f"Scanning: {item.name[:40]}"

                    result = self.check_bitcoin_directory(item)
                    if result:
                        self.found_directories.append(result)
                        sp.write(success(f"✓ Found: {item}"))

                    # Don't recurse into system directories
                    if item.name not in ['System', 'Library', 'Applications', 'private', 'usr', 'bin']:
                        try:
                            self.scan_directory(item, sp)
                        except PermissionError:
                            pass
        except:
            pass

    def scan(self) -> List[Dict]:
        """Perform the scan"""
        self.display_banner()

        search_paths = self.get_search_paths()

        # Show search locations
        console.print(bold("Search Locations:"))
        for p in search_paths:
            console.print(muted(f"  • {p}"))
        console.print()

        # Scan with yaspin spinner
        with yaspin(
            Spinners.dots,
            text="Scanning for Bitcoin directories...",
            color="cyan"
        ) as sp:

            for search_path in search_paths:
                sp.text = f"Scanning: {search_path.name}"

                # Check path itself
                result = self.check_bitcoin_directory(search_path)
                if result:
                    self.found_directories.append(result)
                    sp.write(success(f"✓ Found: {search_path}"))

                # Scan subdirectories
                self.scan_directory(search_path, sp)

            if self.found_directories:
                sp.ok("✓")
                sp.text = "Scan complete"
            else:
                sp.fail("✗")
                sp.text = "No directories found"

        console.print()

        # Display results
        self.display_results()

        return self.found_directories

    def display_results(self):
        """Display scan results"""
        if not self.found_directories:
            console.print(Panel(
                warning("NO BITCOIN DIRECTORIES FOUND") + "\n\n" +
                muted("Ensure Bitcoin Core has been run at least once."),
                title=bold("SCAN RESULTS"),
                border_style="yellow",
                box=box.ASCII
            ))
            return

        # Results table
        table = Table(
            box=box.ASCII,
            border_style="dim white",
            show_header=True,
            header_style="bold white"
        )

        table.add_column("Path", style="white", no_wrap=False)
        table.add_column("Size", justify="right", style="dim")
        table.add_column("Status", justify="center")

        for dir_info in self.found_directories:
            path = dir_info['path']
            size_gb = dir_info['size_gb']
            size_str = f"{size_gb:.1f} GB" if size_gb > 0 else muted("unknown")

            if dir_info['has_blocks'] and dir_info['has_chainstate']:
                status = success("VALID")
            else:
                status = warning("PARTIAL")

            table.add_row(path, size_str, status)

        console.print(Panel(
            table,
            title=bold(f"FOUND {len(self.found_directories)} DIRECTOR{'Y' if len(self.found_directories) == 1 else 'IES'}"),
            border_style="green",
            box=box.ASCII
        ))
        console.print()

        # Summary
        total_size = sum(d['size_gb'] for d in self.found_directories)
        summary = f"Total: {total_size:.1f} GB"
        console.print(muted(summary))
        console.print()

    def save_to_config(self, config) -> bool:
        """Save first found directory to config"""
        if self.found_directories:
            first_dir = Path(self.found_directories[0]['path'])
            config.set_datadir(first_dir)

            console.print(Panel(
                success("SAVED TO CONFIG") + f"\n\n{first_dir}\n\n" +
                muted("Next launch will use this directory automatically."),
                title=bold("CONFIGURATION"),
                border_style="green",
                box=box.ASCII
            ))
            return True
        return False


if __name__ == "__main__":
    scanner = BitcoinScanner()
    scanner.scan()
