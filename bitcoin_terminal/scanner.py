"""
Bitcoin Data Directory Scanner
Searches the local filesystem for Bitcoin Core data directories
"""

import os
import platform
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
import pyfiglet

console = Console()


class BitcoinScanner:
    """Scans for Bitcoin Core data directories"""

    # Common Bitcoin data directory locations by OS
    DEFAULT_PATHS = {
        'Darwin': [  # macOS
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

    # Files that indicate a valid Bitcoin data directory
    BITCOIN_MARKERS = [
        'blocks',
        'chainstate',
        'bitcoin.conf',
        'debug.log',
        '.lock',
    ]

    def __init__(self):
        self.system = platform.system()
        self.found_directories: List[Dict] = []

    def display_banner(self):
        """Display beautiful ASCII banner"""
        title = pyfiglet.figlet_format("BITCOIN", font="slant")
        subtitle = pyfiglet.figlet_format("Terminal", font="small")

        console.print(f"[bold orange1]{title}[/bold orange1]", justify="center")
        console.print(f"[bold white]{subtitle}[/bold white]", justify="center")
        console.print("[dim]🔍 Scanning for Bitcoin Node data directories...[/dim]\n", justify="center")

    def get_search_paths(self) -> List[Path]:
        """Get list of paths to search based on OS"""
        paths = []

        # Add default paths for current OS
        default_paths = self.DEFAULT_PATHS.get(self.system, [])
        for path_str in default_paths:
            expanded = Path(path_str).expanduser()
            if expanded.exists():
                paths.append(expanded)

        # Add mounted volumes (useful for external drives)
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
        """Check if a directory contains Bitcoin data"""
        try:
            markers_found = []

            # Check for Bitcoin marker files/directories
            for marker in self.BITCOIN_MARKERS:
                marker_path = path / marker
                if marker_path.exists():
                    markers_found.append(marker)

            # Need at least 2 markers to consider it valid
            if len(markers_found) >= 2:
                # Try to get directory size
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
        except PermissionError:
            pass
        except Exception as e:
            console.print(f"[dim red]Error scanning {path}: {e}[/dim red]")

        return None

    def scan_directory(self, root: Path, progress, task) -> None:
        """Recursively scan a directory tree"""
        try:
            for item in root.iterdir():
                if item.is_dir():
                    # Update progress
                    progress.update(task, description=f"[cyan]Scanning:[/cyan] {item.name[:40]}")

                    # Check if this is a Bitcoin directory
                    result = self.check_bitcoin_directory(item)
                    if result:
                        self.found_directories.append(result)
                        progress.console.print(f"[green]✓ Found:[/green] {item}")

                    # Don't recurse too deep or into known system directories
                    if item.name not in ['System', 'Library', 'Applications', 'private', 'usr', 'bin', 'sbin']:
                        try:
                            self.scan_directory(item, progress, task)
                        except PermissionError:
                            pass
        except PermissionError:
            pass
        except Exception:
            pass

    def scan(self) -> List[Dict]:
        """Perform the scan"""
        self.display_banner()

        search_paths = self.get_search_paths()

        console.print(Panel(
            f"[bold white]Searching in {len(search_paths)} locations[/bold white]\n" +
            "\n".join([f"[dim]• {p}[/dim]" for p in search_paths]),
            border_style="orange1",
            box=box.ROUNDED
        ))
        console.print()

        with Progress(
            SpinnerColumn(spinner_name="dots", style="orange1"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style="orange1", complete_style="green"),
            TimeElapsedColumn(),
            console=console,
            transient=False
        ) as progress:

            task = progress.add_task("[cyan]Scanning...", total=len(search_paths))

            for search_path in search_paths:
                progress.update(task, description=f"[cyan]Scanning:[/cyan] {search_path.name}")

                # First check if the search path itself is a Bitcoin directory
                result = self.check_bitcoin_directory(search_path)
                if result:
                    self.found_directories.append(result)
                    progress.console.print(f"[green]✓ Found:[/green] {search_path}")

                # Then scan subdirectories (but not too deep)
                self.scan_directory(search_path, progress, task)

                progress.advance(task)

        # Display results
        self.display_results()

        return self.found_directories

    def display_results(self):
        """Display scan results in a beautiful table"""
        console.print()

        if not self.found_directories:
            console.print(Panel(
                "[yellow]⚠️  No Bitcoin data directories found[/yellow]\n\n"
                "[dim]Make sure Bitcoin Core is installed and has been run at least once.[/dim]",
                title="[bold]Scan Complete[/bold]",
                border_style="yellow",
                box=box.ROUNDED
            ))
            return

        # Create results table
        table = Table(
            title="[bold orange1]⚡ Bitcoin Data Directories Found[/bold orange1]",
            box=box.ROUNDED,
            border_style="orange1",
            header_style="bold white",
            show_lines=True
        )

        table.add_column("Path", style="cyan", no_wrap=False)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Blocks", justify="center", style="blue")
        table.add_column("Status", justify="center")

        for dir_info in self.found_directories:
            # Status indicator
            if dir_info['has_blocks'] and dir_info['has_chainstate']:
                status = "[green]✓ Complete[/green]"
            else:
                status = "[yellow]⚠ Partial[/yellow]"

            # Format size
            size_str = f"{dir_info['size_gb']:.1f} GB" if dir_info['size_gb'] > 0 else "[dim]Unknown[/dim]"

            # Blocks indicator
            blocks = "✓" if dir_info['has_blocks'] else "✗"

            table.add_row(
                dir_info['path'],
                size_str,
                blocks,
                status
            )

        console.print(table)
        console.print()

        # Summary
        total_size = sum(d['size_gb'] for d in self.found_directories)
        summary = Text()
        summary.append("📊 Summary: ", style="bold white")
        summary.append(f"Found {len(self.found_directories)} director{'y' if len(self.found_directories) == 1 else 'ies'}", style="green")
        summary.append(f" • Total size: {total_size:.1f} GB", style="blue")

        console.print(Panel(summary, border_style="dim", box=box.ROUNDED))


if __name__ == "__main__":
    scanner = BitcoinScanner()
    scanner.scan()
