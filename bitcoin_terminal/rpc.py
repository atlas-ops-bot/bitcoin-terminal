"""
Bitcoin RPC Client
Handles communication with Bitcoin Core node via RPC
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from pathlib import Path


class BitcoinRPC:
    """Bitcoin Core RPC client"""

    def __init__(self, host: str = '127.0.0.1', port: int = 8332,
                 user: str = '', password: str = ''):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.url = f"http://{host}:{port}"
        self._id_counter = 0

    @classmethod
    def from_datadir(cls, datadir: Path):
        """Create RPC client from Bitcoin data directory"""
        # Try to read bitcoin.conf
        conf_path = datadir / 'bitcoin.conf'
        if not conf_path.exists():
            return cls()

        config = {}
        with open(conf_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()

        return cls(
            host=config.get('rpcconnect', '127.0.0.1'),
            port=int(config.get('rpcport', 8332)),
            user=config.get('rpcuser', ''),
            password=config.get('rpcpassword', '')
        )

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

        # Create request with authentication
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        if self.user and self.password:
            import base64
            credentials = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            req.add_header('Authorization', f'Basic {credentials}')

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                if 'error' in result and result['error']:
                    raise Exception(f"RPC Error: {result['error']}")
                return result.get('result')
        except urllib.error.URLError as e:
            raise ConnectionError(f"Cannot connect to Bitcoin Core: {e}")

    def getblockchaininfo(self) -> Dict:
        """Get blockchain information"""
        return self.call('getblockchaininfo')

    def getnetworkinfo(self) -> Dict:
        """Get network information"""
        return self.call('getnetworkinfo')

    def getmempoolinfo(self) -> Dict:
        """Get mempool information"""
        return self.call('getmempoolinfo')

    def getpeerinfo(self) -> list:
        """Get peer information"""
        return self.call('getpeerinfo')

    def uptime(self) -> int:
        """Get node uptime in seconds"""
        return self.call('uptime')

    def getblockcount(self) -> int:
        """Get current block height"""
        return self.call('getblockcount')

    def getbestblockhash(self) -> str:
        """Get best block hash"""
        return self.call('getbestblockhash')

    def getblock(self, blockhash: str, verbosity: int = 1) -> Dict:
        """Get block information"""
        return self.call('getblock', [blockhash, verbosity])

    def getchaintips(self) -> list:
        """Get information about all known tips in the block tree"""
        return self.call('getchaintips')

    def test_connection(self) -> bool:
        """Test if connection to node is working"""
        try:
            self.getblockcount()
            return True
        except:
            return False
