"""
Etherscan/BscScan V2 API compatible client for ERC20/BSC USDT monitoring.

Etherscan V2 migration: https://docs.etherscan.io/v2-migration
- V2 URL: https://api.etherscan.io/v2/api?chainid=1&...
- BscScan still uses V1: https://api.bscscan.com/api?...
"""
from __future__ import annotations
import json, time, logging
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class ChainTransfer:
    """Standardized transfer event."""
    def __init__(self, tx_hash: str, from_addr: str, to_addr: str,
                 amount: float, block_number: int, block_timestamp_ms: int,
                 chain: str):
        self.tx_hash = tx_hash
        self.from_address = from_addr
        self.to_address = to_addr
        self.amount = amount
        self.block_number = block_number
        self.block_timestamp = block_timestamp_ms
        self.chain = chain


class EtherscanV2Client:
    """
    Etherscan V2 API client.
    Uses: https://api.etherscan.io/v2/api?chainid=1&...
    
    For USDT on Ethereum mainnet:
      contract: 0xdAC17F958D2ee523a2206206994597C13D831ec7
      chainid: 1
    """
    
    def __init__(self, api_key: str = "", chain: str = "ERC20",
                 usdt_contract: str = "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                 chain_id: int = 1):
        self.base_url = "https://api.etherscan.io/v2/api"
        self.api_key = api_key
        self.chain = chain
        self.chain_id = chain_id
        self.usdt_contract = usdt_contract.lower()
    
    def _call(self, params: dict) -> dict:
        params.setdefault("apikey", self.api_key)
        params["chainid"] = self.chain_id
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}?{qs}"
        
        for attempt in range(3):
            try:
                req = Request(url, headers={"Accept": "application/json"})
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                if data.get("status") == "1":
                    return data
                msg = data.get("message", "")
                if "No transactions" in msg:
                    return {"status": "1", "result": []}
                if attempt < 2:
                    logger.warning("Etherscan V2 attempt %d: %s", attempt+1, msg[:50])
                    time.sleep(1)
                    continue
                return data
            except (URLError, OSError, json.JSONDecodeError) as e:
                logger.warning("Etherscan V2 attempt %d error: %s", attempt+1, e)
                if attempt < 2:
                    time.sleep(1 + attempt)
        return {"status": "0", "result": [], "message": "Request failed"}
    
    def get_usdt_transfers_to(self, address: str,
                               since_timestamp_ms: int = 0,
                               limit: int = 50) -> list[ChainTransfer]:
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": self.usdt_contract,
            "address": address,
            "sort": "desc",
            "limit": str(limit),
        }
        if since_timestamp_ms:
            params["starttimestamp"] = str(since_timestamp_ms // 1000)
        
        data = self._call(params)
        transfers = []
        for tx in data.get("result", [])[:limit]:
            to_addr = (tx.get("to") or "").lower()
            if to_addr != address.lower():
                continue
            value = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
            block_ts = int(tx.get("timeStamp", 0)) * 1000
            transfers.append(ChainTransfer(
                tx_hash=tx.get("hash", ""),
                from_addr=tx.get("from", ""),
                to_addr=to_addr,
                amount=round(value, 6),
                block_number=int(tx.get("blockNumber", 0)),
                block_timestamp_ms=block_ts,
                chain=self.chain,
            ))
        return transfers
    
    def get_balance(self, address: str) -> Optional[float]:
        """Get USDT balance via Etherscan tokenbalance endpoint."""
        params = {
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": self.usdt_contract,
            "address": address,
        }
        data = self._call(params)
        result = data.get("result", "")
        if result and isinstance(result, str) and result.isdigit():
            return int(result) / 1e6  # USDT has 6 decimals on Ethereum too? No - 18 actually
        # USDT is 18 decimals on Ethereum mainnet
        if result and isinstance(result, str) and result.lstrip('-').isdigit():
            return int(result) / 1e18
        return None


class BscScanClient:
    """
    BscScan V1 API client (BSC still uses V1).
    URL: https://api.bscscan.com/api
    
    USDT on BSC: 0x55d398326f99059fF775485246999027B3197955
    """
    
    def __init__(self, api_key: str = "", chain: str = "BSC",
                 usdt_contract: str = "0x55d398326f99059fF775485246999027B3197955"):
        self.base_url = "https://api.bscscan.com/api"
        self.api_key = api_key
        self.chain = chain
        self.usdt_contract = usdt_contract.lower()
    
    def _call(self, params: dict) -> dict:
        params.setdefault("apikey", self.api_key)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}?{qs}"
        
        for attempt in range(3):
            try:
                req = Request(url, headers={"Accept": "application/json"})
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                if data.get("status") == "1":
                    return data
                msg = data.get("message", "")
                if "No transactions" in msg:
                    return {"status": "1", "result": []}
                if attempt < 2:
                    logger.warning("BscScan attempt %d: %s", attempt+1, msg[:50])
                    time.sleep(1)
                    continue
                return data
            except (URLError, OSError, json.JSONDecodeError) as e:
                logger.warning("BscScan attempt %d error: %s", attempt+1, e)
                if attempt < 2:
                    time.sleep(1 + attempt)
        return {"status": "0", "result": [], "message": "Request failed"}
    
    def get_usdt_transfers_to(self, address: str,
                               since_timestamp_ms: int = 0,
                               limit: int = 50) -> list[ChainTransfer]:
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": self.usdt_contract,
            "address": address,
            "sort": "desc",
            "limit": str(limit),
        }
        if since_timestamp_ms:
            params["starttimestamp"] = str(since_timestamp_ms // 1000)
        
        data = self._call(params)
        transfers = []
        for tx in data.get("result", [])[:limit]:
            to_addr = (tx.get("to") or "").lower()
            if to_addr != address.lower():
                continue
            value = int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
            block_ts = int(tx.get("timeStamp", 0)) * 1000
            transfers.append(ChainTransfer(
                tx_hash=tx.get("hash", ""),
                from_addr=tx.get("from", ""),
                to_addr=to_addr,
                amount=round(value, 6),
                block_number=int(tx.get("blockNumber", 0)),
                block_timestamp_ms=block_ts,
                chain=self.chain,
            ))
        return transfers
    
    def get_balance(self, address: str) -> Optional[float]:
        params = {
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": self.usdt_contract,
            "address": address,
        }
        data = self._call(params)
        result = data.get("result", "")
        if result and isinstance(result, str) and result.lstrip('-').isdigit():
            return int(result) / 1e18
        return None


# ── Environment configuration ──────────────────────
from app.config import settings


def create_chain_client(chain: str):
    """Create a chain client. Returns None if chain is unsupported or API key missing."""
    chain = chain.upper()
    if chain == "TRC20":
        from app.infrastructure.blockchain.trongrid_client import TrongridClient
        client = TrongridClient()
        client.chain = "TRC20"
        client.usdt_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
        
        def get_usdt_transfers_to(address, since_timestamp_ms=0, limit=50):
            from app.infrastructure.blockchain.trongrid_client import TrongridMonitor
            mon = TrongridMonitor(client)
            raw = mon.fetch_new_transfers(address, since_block=since_timestamp_ms, limit=limit)
            return [ChainTransfer(
                tx_hash=t["tx_hash"], from_addr=t["from_address"],
                to_addr=t["to_address"], amount=t["amount"],
                block_number=t.get("block_number", 0),
                block_timestamp_ms=t.get("block_timestamp", 0),
                chain="TRC20",
            ) for t in raw]
        
        client._tx_fetcher = get_usdt_transfers_to
        return client
    
    elif chain == "ERC20":
        if not settings.ETHERSCAN_API_KEY:
            logger.warning("ETHERSCAN_API_KEY 未配置，跳过 ERC20 监控")
            return None
        return EtherscanV2Client(settings.ETHERSCAN_API_KEY, "ERC20",
            "0xdAC17F958D2ee523a2206206994597C13D831ec7", chain_id=1)
    
    elif chain == "BSC":
        if not settings.BSCSCAN_API_KEY:
            logger.warning("BSCSCAN_API_KEY 未配置，跳过 BSC 监控")
            return None
        return BscScanClient(settings.BSCSCAN_API_KEY, "BSC",
            "0x55d398326f99059fF775485246999027B3197955")
    
    return None
