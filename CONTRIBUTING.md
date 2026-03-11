# Contributing

Thank you for your interest in Bitcoin Terminal.

## Setup

```bash
git clone https://github.com/CRTao/bitcoin-terminal.git
cd bitcoin-terminal
python3 -m venv venv && source venv/bin/activate
pip install -e .
pip install -r requirements.txt
```

## Project Structure

```
bitcoin_terminal/
├── __main__.py        # CLI entry point, setup wizard launcher
├── tui.py             # Main dashboard — 12 cards, CSS Grid layout
├── config_screen.py   # bitcoin.conf editor, save/restart dialog
├── config_data.py     # 100+ field definitions with danger levels
├── rpc.py             # Bitcoin RPC client (cookie / password / rpcauth)
├── data.py            # External API fetchers, price cache, supply math
├── scanner.py         # Auto-detect Bitcoin data directories
├── config.py          # .env configuration management
├── setup_wizard.py    # Guided first-run wizard
├── log_view.py        # Live debug.log viewer
└── ansi_utils.py      # Terminal styling helpers
```

## Stack

| Library | Role |
|---------|------|
| **Textual** | TUI framework (screens, widgets, CSS layout) |
| **Rich** | Panels, tables, styled text |
| **pyfiglet** | ASCII art for hero cards |
| **psutil** | CPU, memory, disk, temperature monitoring |
| **python-dotenv** | `.env` persistence |

## Running

```bash
python -m bitcoin_terminal            # Normal launch
python -m bitcoin_terminal --setup    # Re-run setup wizard
python -m bitcoin_terminal --datadir /path/to/bitcoin
python -m bitcoin_terminal scan       # Scan only
```

## Coding Standards

- Type hints on public functions
- Descriptive names (`scan_for_bitcoin_directories`, not `scan_dirs`)
- Comments only where logic isn't obvious
- No unused imports or dead code

## Commit Messages

```
<type>: <subject>

feat:     New feature
fix:      Bug fix
docs:     Documentation
style:    Formatting, colors, layout
refactor: Code restructure (no behavior change)
test:     Tests
chore:    Maintenance
```

## Pull Request Process

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes and test
4. Commit with clear messages
5. Open a PR

### PR Checklist

- [ ] Code follows project style
- [ ] Tested manually against a running Bitcoin node
- [ ] No sensitive data (keys, passwords) committed
- [ ] Documentation updated if adding features

## Areas to Contribute

- **Cards**: New dashboard widgets (Lightning, fee estimator history, etc.)
- **Themes**: Color theme support
- **Platform**: Windows testing and fixes
- **Tests**: Unit and integration tests
- **Performance**: Reduce API calls, optimize rendering

## License

By contributing you agree your work is licensed under [MIT](LICENSE).
