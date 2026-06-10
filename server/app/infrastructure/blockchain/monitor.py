"""
链上交易监控 Worker — 定时轮询 Trongrid，自动匹配用户提交的充值申请
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.blockchain.trongrid_client import TrongridClient, USDT_CONTRACT
from app.infrastructure.blockchain.chain_client import create_chain_client, ChainTransfer
from app.infrastructure.blockchain.ws_manager import get_ws_manager
from app.infrastructure.persistence.postgres.session import async_session_factory

logger = logging.getLogger(__name__)

POLL_INTERVAL = 45  # seconds between polls
CONFIRM_THRESHOLD = 1  # block confirmations needed


class BlockchainMonitorWorker:
    """Background worker that polls blockchain for incoming USDT transfers."""

    def __init__(self):
        self.client = TrongridClient()
        self._running = False

    async def start(self):
        """Start the monitor loop."""
        if self._running:
            return
        self._running = True
        logger.info("BlockchainMonitorWorker started (poll every %ds)", POLL_INTERVAL)
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error("Monitor poll error: %s", e)
            await asyncio.sleep(POLL_INTERVAL)

    async def stop(self):
        """Stop the monitor."""
        self._running = False
        logger.info("BlockchainMonitorWorker stopped")

    async def _poll_once(self):
        """One poll cycle: check all platform addresses for new transfers."""
        async with async_session_factory() as session:
            # 1. Get all ACTIVE platform deposit addresses
            addrs = await session.execute(text(
                "SELECT id, chain, address FROM deposit_addresses "
                "WHERE owner_type='PLATFORM' AND status='ACTIVE'"
            ))
            platform_addrs = addrs.all()

            if not platform_addrs:
                return

            for addr_row in platform_addrs:
                da_id, chain, address = addr_row

                try:
                    await self._check_address(session, da_id, chain, address)
                except Exception as e:
                    logger.error("Error checking %s %s: %s", chain, address[:12], e)
                    # Update monitor state with error
                    await session.execute(text(
                        "INSERT INTO blockchain_monitor_state (chain, address, last_error, updated_at) "
                        "VALUES (:ch, :addr, :err, NOW()) "
                        "ON CONFLICT (chain, address) DO UPDATE SET last_error=:err2, updated_at=NOW()"
                    ).bindparams(ch=chain, addr=address, err=str(e)[:500], err2=str(e)[:500]))
                    await session.commit()

    async def _check_address(self, session: AsyncSession, da_id: int,
                              chain: str, address: str):
        """Check a platform address for new transfers using the appropriate chain client."""
        # Get the last timestamp cursor (stored in ms)
        state = await session.execute(
            text("SELECT COALESCE(last_block_ts, 0) FROM blockchain_monitor_state "
                 "WHERE chain=:ch AND address=:addr")
            .bindparams(ch=chain, addr=address))
        s = state.scalar() or 0
        last_ts_ms = s

        # Get the chain-specific client
        client = create_chain_client(chain)
        if client is None:
            logger.warning("Unsupported chain: %s", chain)
            return

        # Fetch transfers since last checkpoint (with 60s overlap)
        since_ms = last_ts_ms - 60000 if last_ts_ms > 0 else 0
        # Get the fetch function (supports both client.get_usdt_transfers_to and client._tx_fetcher)
        fetcher = getattr(client, 'get_usdt_transfers_to', None) or getattr(client, '_tx_fetcher', None)
        if fetcher is None:
            logger.warning("No fetch method for chain %s", chain)
            return
        transfers = fetcher(address, since_timestamp_ms=since_ms, limit=50)

        if not transfers:
            # Update poll count even if no new txns
            await session.execute(text(
                "INSERT INTO blockchain_monitor_state (chain, address, poll_count, updated_at) "
                "VALUES (:ch, :addr, 1, NOW()) "
                "ON CONFLICT (chain, address) DO UPDATE SET "
                "poll_count=blockchain_monitor_state.poll_count+1, "
                "last_error=NULL, updated_at=NOW()"
            ).bindparams(ch=chain, addr=address))
            await session.commit()
            return

        new_count = 0
        max_ts_ms = last_ts_ms

        for tx in transfers:
            tx_hash = tx.tx_hash
            amount = tx.amount
            block_ts = tx.block_timestamp
            from_addr = tx.from_address

            if block_ts > max_ts_ms:
                max_ts_ms = block_ts

            # Skip if we already have this tx_hash
            existing = await session.execute(
                text("SELECT id FROM blockchain_txns WHERE chain=:ch AND tx_hash=:h")
                .bindparams(ch=chain, h=tx_hash))
            if existing.first():
                continue

            # Try to match against pending deposits
            deposit_id = await self._match_deposit(session, tx_hash, amount)
            status = "MATCHED" if deposit_id else "UNMATCHED"

            await session.execute(text(
                "INSERT INTO blockchain_txns (chain, tx_hash, from_address, to_address, "
                "amount, block_number, status, deposit_id, created_at) "
                "VALUES (:ch, :h, :f, :to, :amt, :bn, :st, :did, NOW()) "
                "ON CONFLICT (chain, tx_hash) DO NOTHING"
            ).bindparams(
                ch=chain, h=tx_hash, f=from_addr, to=address,
                amt=float(amount), bn=block_ts // 1000, st=status,
                did=deposit_id or 0,
            ))

            if deposit_id:
                await self._auto_confirm_deposit(session, deposit_id, tx_hash, amount)

            new_count += 1

        # Update monitor state with new timestamp cursor
        await session.execute(text(
            "INSERT INTO blockchain_monitor_state (chain, address, last_block, last_block_ts, poll_count, updated_at) "
            "VALUES (:ch, :addr, :lb, :ts, 1, NOW()) "
            "ON CONFLICT (chain, address) DO UPDATE SET "
            "last_block=GREATEST(blockchain_monitor_state.last_block, :lb2), "
            "last_block_ts=GREATEST(blockchain_monitor_state.last_block_ts, :ts2), "
            "poll_count=blockchain_monitor_state.poll_count+1, "
            "last_error=NULL, updated_at=NOW()"
        ).bindparams(ch=chain, addr=address, lb=max_ts_ms // 1000, ts=max_ts_ms,
                     lb2=max_ts_ms // 1000, ts2=max_ts_ms))
        await session.commit()

        if new_count > 0:
            logger.info("Checked %s %s → %d new txns",
                        chain, address[:12], new_count)
            # Broadcast
            ws_msg = {
                "type": "new_transactions",
                "count": new_count,
                "matched": deposit_id is not None,
                "address": address[:16],
                "chain": chain,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            try:
                await get_ws_manager().broadcast(ws_msg)
            except Exception:
                pass

    def _fetch_trc20_to_address(self, address: str, since_block: int = 0) -> list:
        """
        Fetch TRC20 USDT transfers to the given address.
        Uses the events API endpoint.
        """
        params = {"limit": 30, "event_name": "Transfer", "only_confirmed": "true"}
        if since_block:
            params["min_block_timestamp"] = since_block

        url = f"{self.client.base_url}/v1/contracts/{USDT_CONTRACT}/events"
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v)

        import json, time as ttime
        from urllib.request import Request, urlopen

        all_transfers = []
        next_fingerprint = ""

        # Poll up to 2 pages (60 txns)
        for page in range(2):
            fetch_url = f"{url}?{qs}"
            if next_fingerprint:
                fetch_url += f"&fingerprint={next_fingerprint}"

            try:
                req = Request(fetch_url, headers=self.client.headers)
                with urlopen(req, timeout=15) as resp:
                    raw = json.loads(resp.read())
            except Exception as e:
                logger.warning("Fetch error (page %d): %s", page, e)
                break

            if not raw.get("success", True):
                break

            target = address.lower()
            # Convert base58 address to hex for comparison (events always return hex)
            target_hex = target
            if target.startswith('t'):
                import base58 as b58mod
                try:
                    decoded = b58mod.b58decode(target)
                    target_hex = '0x' + decoded[1:-4].hex()
                except:
                    pass

            for event in raw.get("data", []):
                result = event.get("result", {})
                event_to = (result.get("to", "") or "").lower()

                if event_to != target_hex:
                    continue

                value = int(result.get("value", 0)) / 1e6

                # Dust filter: skip transactions < 1 USDT
                if value < 1.0:
                    continue

                block_ts = event.get("block_timestamp", 0)
                all_transfers.append({
                    "tx_hash": event.get("transaction_id", ""),
                    "from_address": result.get("from", ""),
                    "to_address": result.get("to", ""),
                    "amount": round(value, 6),
                    "block_number": event.get("block_number", 0),
                    "block_timestamp": block_ts,
                    "block_ts_str": ttime.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    ttime.gmtime(block_ts / 1000)) if block_ts else "",
                })

            # Check next page
            meta = raw.get("meta", {})
            links = meta.get("links", {}) if meta.get("links") else {}
            next_fingerprint = meta.get("fingerprint", "") or links.get("next", "")
            if not next_fingerprint:
                break

        return all_transfers

    async def _match_deposit(self, session: AsyncSession,
                              tx_hash: str, amount: float) -> Optional[int]:
        """
        Try to match a detected on-chain transaction with a pending deposit.
        Matches by tx_hash first, then by amount + approximate time.
        """
        # Exact match by tx_hash (user submitted this tx_hash)
        row = await session.execute(
            text("SELECT id, amount FROM deposits WHERE tx_hash=:h AND status='PENDING' LIMIT 1")
            .bindparams(h=tx_hash))
        r = row.first()
        if r:
            return r[0]

        # Fuzzy match: same amount within last 24h
        # (handles case where user didn't submit tx_hash yet, or submitted wrong one)
        row = await session.execute(
            text("SELECT id, amount FROM deposits "
                 "WHERE status='PENDING' AND amount=:amt "
                 "AND created_at > NOW() - INTERVAL '24 hours' "
                 "ORDER BY created_at DESC LIMIT 1")
            .bindparams(amt=int(amount)))  # amount stored as bigint in deposits
        r = row.first()
        if r:
            return r[0]

        return None

    async def _auto_confirm_deposit(self, session: AsyncSession,
                                     deposit_id: int, tx_hash: str, amount: float):
        """Auto-confirm a deposit and credit points to the user's wallet."""
        # Get deposit details
        dep = await session.execute(
            text("SELECT owner_type, owner_id, wallet_id FROM deposits WHERE id=:id")
            .bindparams(id=deposit_id))
        d = dep.first()
        if not d:
            return

        owner_type, owner_id, wallet_id = d

        # Update deposit status
        await session.execute(
            text("UPDATE deposits SET status='CONFIRMED', confirmed_at=NOW(), "
                 "admin_note='链上自动确认' WHERE id=:id")
            .bindparams(id=deposit_id))

        # Credit wallet
        if wallet_id:
            await session.execute(
                text("UPDATE wallets SET balance=balance+:amt, updated_at=NOW() WHERE id=:wid")
                .bindparams(amt=int(amount), wid=wallet_id))

            # Log transaction
            await session.execute(
                text("INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, "
                     "related_order_no, remark, created_at) "
                     "SELECT :wid, 'DEPOSIT', :amt, balance-:amt2, balance, NULL, '链上自动充值', NOW() "
                     "FROM wallets WHERE id=:wid3")
                .bindparams(wid=wallet_id, amt=int(amount), amt2=int(amount), wid3=wallet_id))

        logger.info("Auto-confirmed deposit #%d for %s USDT (tx: %s)", deposit_id, amount, tx_hash[:16])


# Singleton instance
_monitor: Optional[BlockchainMonitorWorker] = None


async def start_monitor():
    """Start the blockchain monitor worker."""
    global _monitor
    if _monitor is not None:
        return
    _monitor = BlockchainMonitorWorker()
    asyncio.create_task(_monitor.start())


async def stop_monitor():
    """Stop the blockchain monitor worker."""
    global _monitor
    if _monitor:
        await _monitor.stop()
        _monitor = None
