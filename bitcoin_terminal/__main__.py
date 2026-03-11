"""
Main entry point for Bitcoin Terminal
Smart launcher: runs setup wizard on first run, then launches TUI
"""

import sys
import argparse
from pathlib import Path
from bitcoin_terminal.scanner import BitcoinScanner
from bitcoin_terminal.tui import BitcoinTUI
from bitcoin_terminal.config import Config
from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console()


def run_setup_wizard(config: Config) -> bool:
    """Run the interactive setup wizard. Returns True if completed."""
    from textual.app import App, ComposeResult
    from bitcoin_terminal.setup_wizard import SetupWizard

    class WizardApp(App):
        CSS = "Screen { background: #0a0a0a; }"

        def __init__(self, cfg: Config):
            super().__init__()
            self._cfg = cfg
            self.wizard_completed = False

        def on_mount(self) -> None:
            self.push_screen(
                SetupWizard(self._cfg),
                callback=self._on_wizard_done,
            )

        def _on_wizard_done(self, result: bool) -> None:
            self.wizard_completed = bool(result)
            self.exit()

    app = WizardApp(config)
    app.run()
    return app.wizard_completed


def main():
    """Main entry point with smart directory detection"""
    parser = argparse.ArgumentParser(
        description="Bitcoin Terminal - Monitor your Bitcoin Node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'command',
        nargs='?',
        choices=['scan', 'run'],
        default='run',
        help='Command to execute (scan: search for Bitcoin dirs, run: start TUI)'
    )

    parser.add_argument(
        '--datadir',
        type=str,
        help='Path to Bitcoin data directory (overrides auto-detection)'
    )

    parser.add_argument(
        '--force-scan',
        action='store_true',
        help='Force re-scan even if directory is configured'
    )

    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run the setup wizard (even if already configured)'
    )

    args = parser.parse_args()

    try:
        config = Config()

        # Handle explicit scan command
        if args.command == 'scan' or args.force_scan:
            run_scan(config)
            return

        # Run setup wizard on first run or if --setup flag is passed
        if args.setup or config.is_first_run():
            completed = run_setup_wizard(config)
            if not completed:
                console.print("\n[yellow]Setup cancelled.[/yellow]")
                sys.exit(0)
            # Reload config after wizard saves
            config = Config()

        # Check if user provided datadir via command line
        if args.datadir:
            datadir = Path(args.datadir)
            if not datadir.exists():
                console.print(f"[red]❌ Error: Directory not found: {datadir}[/red]")
                sys.exit(1)

            console.print(Panel(
                f"[cyan]Using specified directory:[/cyan]\n{datadir}",
                border_style="blue",
                box=box.ROUNDED
            ))
            launch_tui(datadir)
            return

        # Smart detection: check if we have a valid directory in .env
        datadir = config.get_datadir()

        if datadir and datadir.exists():
            # Valid directory found in config
            console.print(Panel(
                f"[green]✓ Found configured directory:[/green]\n{datadir}\n\n"
                "[dim]Use --setup to re-run the setup wizard[/dim]",
                border_style="green",
                box=box.ROUNDED
            ))
            launch_tui(datadir)
        else:
            # No valid directory after wizard — try auto-scan fallback
            console.print(Panel(
                "[yellow]⚠️  No Bitcoin directory configured[/yellow]\n\n"
                "[white]Running automatic scan...[/white]",
                border_style="yellow",
                box=box.ROUNDED
            ))
            console.print()

            scanner = BitcoinScanner()
            results = scanner.scan()

            if results:
                # Save first result to config
                scanner.save_to_config(config)
                datadir = Path(results[0]['path'])

                # Launch TUI
                console.print()
                console.print("[cyan]🚀 Launching Bitcoin Terminal...[/cyan]")
                console.print()
                launch_tui(datadir)
            else:
                console.print()
                console.print(Panel(
                    "[red]❌ No Bitcoin directories found[/red]\n\n"
                    "[yellow]Please ensure Bitcoin Core is installed and has been run at least once.[/yellow]\n\n"
                    "[dim]You can also specify a directory manually:\n"
                    "python -m bitcoin_terminal --datadir /path/to/bitcoin\n"
                    "Or run the setup wizard:\n"
                    "python -m bitcoin_terminal --setup[/dim]",
                    title="[bold]Scan Failed[/bold]",
                    border_style="red",
                    box=box.ROUNDED
                ))
                sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_scan(config: Config):
    """Run scanner and save result"""
    scanner = BitcoinScanner()
    results = scanner.scan()

    if results:
        scanner.save_to_config(config)
        console.print()
        console.print("[green]✓ Scan complete! Run 'python -m bitcoin_terminal' to launch the TUI.[/green]")
    else:
        console.print()
        console.print("[yellow]⚠️  No Bitcoin directories found.[/yellow]")


def launch_tui(datadir: Path):
    """Launch the TUI application"""
    app = BitcoinTUI(datadir=str(datadir))
    app.run()


if __name__ == "__main__":
    main()
