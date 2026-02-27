# Contributing to Bitcoin Terminal 🤝

Thank you for your interest in contributing! This project aims to be the most beautiful and functional Bitcoin Node TUI available.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/bitcoin-terminal.git
cd bitcoin-terminal

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .
pip install -r requirements.txt
```

## Project Structure

```
bitcoin-terminal/
├── bitcoin_terminal/
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # CLI entry point
│   ├── scanner.py           # Bitcoin directory scanner
│   ├── tui.py               # Main TUI application
│   ├── rpc.py               # Bitcoin RPC client
│   └── config.py            # Configuration management
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup
└── README.md
```

## Design Philosophy

Inspired by [warden_terminal](https://github.com/pxsocs/warden_terminal), we follow these principles:

1. **Beautiful by Default**: Every interface should look amazing
2. **Fast & Responsive**: No lag, smooth animations
3. **Informative**: Show what matters, hide complexity
4. **Modular**: Easy to extend with new features
5. **User-Friendly**: Intuitive keyboard shortcuts and navigation

## Technology Stack

- **Textual**: Modern TUI framework (main dashboard)
- **Rich**: Beautiful terminal output (colors, tables, progress bars)
- **PyFiglet**: ASCII art for branding
- **Python 3.8+**: Core language

## Areas for Contribution

### 🎨 UI/UX Improvements
- Additional color themes
- New dashboard widgets
- Better animations
- Responsive layouts

### 📊 Features
- Block explorer integration
- Transaction mempool viewer
- Peer connection map
- Network statistics graphs
- Lightning Network integration
- Hardware monitoring (CPU, RAM, disk I/O)

### 🔧 Technical
- Windows compatibility testing
- Performance optimizations
- Better error handling
- Unit tests
- Documentation improvements

### 🐛 Bug Fixes
- Check the [Issues](https://github.com/yourusername/bitcoin-terminal/issues) page
- Report bugs you find
- Fix existing issues

## Coding Standards

```python
# Use type hints
def get_block_height(rpc: BitcoinRPC) -> int:
    return rpc.getblockcount()

# Clear, descriptive names
def scan_for_bitcoin_directories() -> List[Path]:
    pass

# Document complex functions
def calculate_sync_percentage(current: int, total: int) -> float:
    """
    Calculate blockchain sync percentage.

    Args:
        current: Current block height
        total: Target block height

    Returns:
        Percentage (0.0 to 100.0)
    """
    return (current / total) * 100 if total > 0 else 0.0
```

## Commit Message Format

```
<type>: <subject>

<body>

Co-Authored-By: Your Name <your.email@example.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting, colors
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

**Examples:**
```
feat: Add Lightning Network support

- Integrate lnd RPC client
- Display channel balance
- Show peer connections

Co-Authored-By: Jane Doe <jane@example.com>
```

## Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feat/amazing-feature`)
3. **Make** your changes
4. **Test** thoroughly
5. **Commit** with clear messages
6. **Push** to your fork
7. **Open** a Pull Request

### PR Checklist

- [ ] Code follows project style
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] Screenshots for UI changes

## Testing

```bash
# Run the scanner
python -m bitcoin_terminal scan

# Run the TUI
python -m bitcoin_terminal

# Test with custom datadir
python -m bitcoin_terminal --datadir /path/to/bitcoin
```

## Getting Help

- 💬 Open a [Discussion](https://github.com/yourusername/bitcoin-terminal/discussions)
- 🐛 File an [Issue](https://github.com/yourusername/bitcoin-terminal/issues)
- 📧 Contact maintainers

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the [Contributor Covenant](https://www.contributor-covenant.org/)

## Recognition

Contributors will be:
- Listed in README.md
- Mentioned in release notes
- Included in AUTHORS file

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Ready to contribute? **Let's build something awesome!** ⚡🟠
