"""
Main entry point for Bitcoin Terminal
"""

import sys
import argparse
from bitcoin_terminal.scanner import BitcoinScanner
from bitcoin_terminal.tui import BitcoinTUI
from rich.console import Console

console = Console()


def main():
    """Main entry point"""
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
        help='Path to Bitcoin data directory'
    )

    args = parser.parse_args()

    try:
        if args.command == 'scan':
            # Run scanner only
            scanner = BitcoinScanner()
            scanner.scan()
        else:
            # Run full TUI
            app = BitcoinTUI(datadir=args.datadir)
            app.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
