"""
Configuration management for Bitcoin Terminal
"""

import os
from pathlib import Path
from typing import Optional
import configparser


class Config:
    """Configuration manager"""

    DEFAULT_CONFIG = {
        'bitcoin': {
            'datadir': '',
            'rpc_host': '127.0.0.1',
            'rpc_port': '8332',
            'rpc_user': '',
            'rpc_password': '',
        },
        'display': {
            'theme': 'dark',
            'refresh_interval': '5',
            'show_mempool': 'true',
            'show_peers': 'true',
        }
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / '.config' / 'bitcoin-terminal' / 'config.ini'

        self.config_path = config_path
        self.config = configparser.ConfigParser()

        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load or create config
        if self.config_path.exists():
            self.load()
        else:
            self.create_default()

    def load(self):
        """Load configuration from file"""
        self.config.read(self.config_path)

    def save(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            self.config.write(f)

    def create_default(self):
        """Create default configuration"""
        for section, options in self.DEFAULT_CONFIG.items():
            self.config[section] = options
        self.save()

    def get(self, section: str, key: str, fallback: str = '') -> str:
        """Get configuration value"""
        return self.config.get(section, key, fallback=fallback)

    def set(self, section: str, key: str, value: str):
        """Set configuration value"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config[section][key] = value
        self.save()

    def get_datadir(self) -> Optional[Path]:
        """Get Bitcoin data directory"""
        datadir = self.get('bitcoin', 'datadir')
        if datadir:
            return Path(datadir)
        return None

    def set_datadir(self, path: Path):
        """Set Bitcoin data directory"""
        self.set('bitcoin', 'datadir', str(path))
