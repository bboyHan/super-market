"""
Trongrid API 客户端 — 查询 TRC20 USDT 交易
文档: https://developers.tron.network/reference
"""
import json, time, logging
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

TRONGRID_API = "https://api.trongrid.io"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

logger = logging.getLogger(__name__)


class TrongridClient:
    """Low-level Trongrid REST API client."""

    def __init__(self, api_key: str = "", base_url: str = TRONGRID_API):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Accept": "application/json"}
        if api_key:
            self.headers["TRON-PRO-API-KEY"] = api_key

    def _get(self, path: str, params: dict = None) -> dict:
        """GET request with retry."""
        url = f"{self.base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            url += f"?{qs}"

        for attempt in range(3):
            try:
                req = Request(url, headers=self.headers)
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                if not data.get("success", True):
                    logger.warning("Trongrid API error: %s", data.get("error", ""))
                    return data
                return data
            except (URLError, OSError, json.JSONDecodeError) as e:
                logger.warning("Trongrid GET %s attempt %d failed: %s", path[:40], attempt + 1, e)
                if attempt < 2:
                    time.sleep(1 + attempt)
        return {"success": False, "error": f"Request failed after 3 attempts", "data": []}

    def get_usdt_transfers(self, address: str, limit: int = 50,
                           min_timestamp: int = 0,
                           fingerprint: str = "") -> dict:
        """
        获取指定 TRC20 地址的 USDT 转账事件。
        Returns: {"data": [...], "meta": {"fingerprint": "...", ...}}
        """
        params = {
            "limit": limit,
            "event_name": "Transfer",
            "only_confirmed": "true",
        }
        if min_timestamp:
            params["min_block_timestamp"] = min_timestamp
        if fingerprint:
            params["fingerprint"] = fingerprint

        # Trongrid events endpoint needs the contract address
        path = f"/v1/contracts/{USDT_CONTRACT}/events"
        data = self._get(path, params)
        return data

    def get_account_balance(self, address: str) -> Optional[float]:
        """Get TRC20 USDT balance for an address. Returns USDT amount or None."""
        path = f"/v1/accounts/{address}"
        data = self._get(path)
        if not data.get("data"):
            # Maybe hex format needed
            path = f"/v1/accounts/{address}"
            data = self._get(f"/v1/accounts?address={address}")
            if not data.get("data"):
                return None

        account = data["data"][0] if data.get("data") else {}
        for token in account.get("assetV2", []):
            if token.get("key", "") == USDT_CONTRACT or token.get("tokenId", "") == USDT_CONTRACT:
                return int(token["value"]) / 1e6
        # Maybe trc20 format
        for token in account.get("trc20", []):
            if USDT_CONTRACT in token:
                return int(token[USDT_CONTRACT]) / 1e6
        return 0.0

    def get_transaction_info(self, tx_hash: str) -> Optional[dict]:
        """Get transaction info by hash."""
        path = f"/v1/transactions/{tx_hash}"
        data = self._get(path)
        if data.get("data"):
            return data["data"][0]
        return None

    def get_latest_block(self) -> int:
        """Get latest block number."""
        data = self._get("/v1/blocks?limit=1&sort=-number")
        if data.get("data"):
            return data["data"][0].get("blockNumber", 0)
        return 0


class TrongridMonitor:
    """High-level monitor that fetches USDT transfers and parses them."""

    def __init__(self, client: TrongridClient = None):
        self.client = client or TrongridClient()

    def fetch_new_transfers(self, address: str, since_block: int = 0,
                            limit: int = 50) -> list[dict]:
        """
        Fetch new USDT transfers TO a platform address.
        Returns list of parsed transfer events.
        """
        params = {
            "limit": limit,
            "event_name": "Transfer",
            "only_confirmed": "true",
            "contract_address": USDT_CONTRACT,
        }
        if since_block:
            params["min_block_timestamp"] = since_block

        # We need to use the /events endpoint differently
        url = f"{self.client.base_url}/v1/contracts/{USDT_CONTRACT}/events"
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{qs}"

        req = Request(full_url, headers=self.client.headers)
        try:
            with urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read())
        except Exception as e:
            logger.error("fetch_new_transfers failed: %s", e)
            return []

        transfers = []
        for event in raw.get("data", []):
            result = event.get("result", {})
            event_to = result.get("to", "").lower()
            target = address.lower()

            # Tron addresses can be in hex (0x...) or base58 format
            # The event result usually has hex addresses
            if target.startswith("0x"):
                target_hex = target
                target_b58 = ""
            else:
                target_hex = ""
                target_b58 = target

            # Check if this transfer is TO our platform address
            matched = False
            if target_hex and event_to == target_hex:
                matched = True
            elif target_b58:
                # Try both formats
                if event_to == target_b58 or event_to == target_b58.lower():
                    matched = True

            if matched:
                value = int(result.get("value", 0)) / 1e6
                block_ts = event.get("block_timestamp", 0)
                transfers.append({
                    "tx_hash": event.get("transaction_id", ""),
                    "from_address": result.get("from", ""),
                    "to_address": result.get("to", ""),
                    "amount": value,
                    "block_number": event.get("block_number", 0),
                    "block_timestamp": block_ts,
                    "block_ts_str": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   time.gmtime(block_ts / 1000)) if block_ts else "",
                })

        return transfers
