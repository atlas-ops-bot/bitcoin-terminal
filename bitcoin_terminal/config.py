"""
Configuration management for Bitcoin Terminal
Uses .env file for persistent storage
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key, find_dotenv


class Config:
    """Configuration manager using .env file"""

    def __init__(self, env_path: Optional[Path] = None):
        """Initialize config, loading from .env if it exists"""
        if env_path is None:
            # Look for .env in project root first
            project_root = Path(__file__).parent.parent
            env_path = project_root / '.env'
            # If not found, walk up the directory tree
            if not env_path.exists():
                found = find_dotenv(usecwd=True)
                if found:
                    env_path = Path(found)

        self.env_path = env_path

        # Load .env if it exists
        if self.env_path.exists():
            load_dotenv(self.env_path)
        else:
            # Create empty .env in project root
            self.env_path.touch()

    def get_datadir(self) -> Optional[Path]:
        """Get Bitcoin data directory from .env"""
        datadir = os.getenv('BITCOIN_DATADIR', '').strip()
        if datadir:
            path = Path(datadir)
            # Validate that the directory exists
            if path.exists():
                return path
        return None

    def set_datadir(self, path: Path):
        """Save Bitcoin data directory to .env"""
        set_key(self.env_path, 'BITCOIN_DATADIR', str(path))
        # Reload environment
        load_dotenv(self.env_path, override=True)

    def get_rpc_config(self) -> dict:
        """Get RPC configuration from .env"""
        return {
            'host': os.getenv('BITCOIN_RPC_HOST', '127.0.0.1'),
            'port': int(os.getenv('BITCOIN_RPC_PORT', '8332')),
            'user': os.getenv('BITCOIN_RPC_USER', ''),
            'password': os.getenv('BITCOIN_RPC_PASSWORD', ''),
        }

    def get_display_config(self) -> dict:
        """Get display configuration from .env"""
        return {
            'refresh_interval': int(os.getenv('REFRESH_INTERVAL', '5')),
            'theme': os.getenv('THEME', 'dark'),
        }

    def is_datadir_configured(self) -> bool:
        """Check if a valid data directory is configured"""
        return self.get_datadir() is not None
