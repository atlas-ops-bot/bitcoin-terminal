"""
Bitcoin RPC Client
Handles communication with Bitcoin Core node via RPC
Supports password auth, rpcauth, and .cookie file auth
"""

import json
import base64
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple
from pathlib import Path


class BitcoinRPC:
    """Bitcoin Core RPC client"""

    # Chain-specific subdirectories where .cookie might live
    CHAIN_DIRS = ['', 'signet', 'testnet3', 'testnet4', 'regtest']

    def __init__(self, host: str = '127.0.0.1', port: int = 8332,
                 user: str = '', password: str = '',
                 datadir: Path = None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.datadir = datadir
        self.url = f"http://{host}:{port}"
        self._id_counter = 0
        self.auth_method = 'none'
        if user and password:
            self.auth_method = 'cookie' if user == '__cookie__' else 'password'

    @classmethod
    def from_datadir(cls, datadir: Path, env_config: dict = None) -> 'BitcoinRPC':
        """Create RPC client from Bitcoin data directory.

        Auth priority:
        1. .env credentials (BITCOIN_RPC_USER/PASSWORD)
        2. rpcuser + rpcpassword from bitcoin.conf
        3. .cookie file (checked in datadir and chain subdirectories)
        """
        # Start with .env credentials if provided
        env_config = env_config or {}
        host = env_config.get('host', '')
        port = env_config.get('port', 0)
        user = env_config.get('user', '')
        password = env_config.get('password', '')

        # Read bitcoin.conf for anything not set via .env
        conf = {}
        conf_path = datadir / 'bitcoin.conf'
        if conf_path.exists():
            conf = cls._parse_bitcoin_conf(conf_path)

        host = host or conf.get('rpcconnect', '127.0.0.1')
        port = port or int(conf.get('rpcport', 8332))

        # If no .env credentials, try bitcoin.conf
        if not user or not password:
            user = user or conf.get('rpcuser', '')
            password = password or conf.get('rpcpassword', '')

        # Extract username from rpcauth= if no explicit rpcuser
        if not user:
            rpcauth = conf.get('rpcauth', '')
            if rpcauth and ':' in rpcauth:
                user = rpcauth.split(':')[0]
                # rpcauth password isn't stored in conf - need .cookie

        # If credentials still incomplete, try .cookie file
        if not user or not password:
            cookie_user, cookie_pass = cls._find_cookie(datadir)
            if cookie_user and cookie_pass:
                user = cookie_user
                password = cookie_pass

        return cls(host=host, port=port, user=user, password=password,
                   datadir=datadir)

    @staticmethod
    def _parse_bitcoin_conf(conf_path: Path) -> Dict[str, str]:
        """Parse bitcoin.conf, handling inline comments and sections."""
        config = {}
        try:
            with open(conf_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('['):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Strip inline comments (but not in passwords)
                        key = key.strip()
                        value = value.strip()
                        if key not in ('rpcpassword',):
                            value = value.split('#')[0].strip()
                        config[key] = value
        except (OSError, IOError):
            pass
        return config

    @classmethod
    def _find_cookie(cls, datadir: Path) -> Tuple[str, str]:
        """Find and read .cookie file, checking chain subdirectories."""
        for chain_dir in cls.CHAIN_DIRS:
            cookie_dir = datadir / chain_dir if chain_dir else datadir
            cookie_path = cookie_dir / '.cookie'
            try:
                if cookie_path.exists():
                    content = cookie_path.read_text().strip()
                    if ':' in content:
                        user, password = content.split(':', 1)
                        return user, password
            except (OSError, IOError):
                continue
        return '', ''

    def _get_auth_header(self) -> str:
        """Get current auth header, re-reading cookie if needed."""
        user = self.user
        password = self.password

        # Re-read cookie on each call (cookie changes on node restart)
        if self.datadir and (not user or not password or user == '__cookie__'):
            cookie_user, cookie_pass = self._find_cookie(self.datadir)
            if cookie_user and cookie_pass:
                user = cookie_user
                password = cookie_pass
                self.user = user
                self.password = password

        if user and password:
            credentials = base64.b64encode(
                f"{user}:{password}".encode()
            ).decode()
            return f'Basic {credentials}'
        return ''

    def call(self, method: str, params: list = None) -> Any:
        """Make RPC call to Bitcoin Core"""
        if params is None:
            params = []

        self._id_counter += 1

        payload = {
            'jsonrpc': '2.0',
            'id': self._id_counter,
            'method': method,
            'params': params
        }

        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        auth = self._get_auth_header()
        if auth:
            req.add_header('Authorization', auth)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                if 'error' in result and result['error']:
                    raise Exception(
                        f"RPC Error ({method}): {result['error']}")
                return result.get('result')
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ConnectionError(
                    f"Authentication failed (HTTP 401). "
                    f"Auth method: {self.auth_method}. "
                    f"Check rpcuser/rpcpassword in bitcoin.conf "
                    f"or ensure .cookie file is readable."
                )
            elif e.code == 403:
                raise ConnectionError(
                    f"Access forbidden (HTTP 403). "
                    f"Check rpcallowip in bitcoin.conf."
                )
            raise ConnectionError(f"HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Cannot connect to {self.url}: {e.reason}")

    def getblockchaininfo(self) -> Dict:
        return self.call('getblockchaininfo')

    def getnetworkinfo(self) -> Dict:
        return self.call('getnetworkinfo')

    def getmempoolinfo(self) -> Dict:
        return self.call('getmempoolinfo')

    def getpeerinfo(self) -> list:
        return self.call('getpeerinfo')

    def uptime(self) -> int:
        return self.call('uptime')

    def getblockcount(self) -> int:
        return self.call('getblockcount')

    def getbestblockhash(self) -> str:
        return self.call('getbestblockhash')

    def getblock(self, blockhash: str, verbosity: int = 1) -> Dict:
        return self.call('getblock', [blockhash, verbosity])

    def getblockhash(self, height: int) -> str:
        return self.call('getblockhash', [height])

    def getblockstats(self, hash_or_height, stats=None) -> Dict:
        params = [hash_or_height]
        if stats:
            params.append(stats)
        return self.call('getblockstats', params)

    def getchaintips(self) -> list:
        return self.call('getchaintips')

    def test_connection(self) -> bool:
        """Test if connection to node is working"""
        try:
            self.getblockcount()
            return True
        except Exception:
            return False
