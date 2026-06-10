from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.routing.strategy import (
    PriorityStrategy,
    RoundRobinStrategy,
    RoutingStrategy,
    WeightedStrategy,
)

# Map strategy names to strategy instances
_STRATEGY_MAP: dict[str, RoutingStrategy] = {
    "ROUND_ROBIN": RoundRobinStrategy(),
    "PRIORITY": PriorityStrategy(),
    "WEIGHTED": WeightedStrategy(),
}


class RoutingEngine:
    """Core routing engine: queries routing rules and picks the best agent."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def select_agent(
        self, product_id: int, supplier_id: int
    ) -> int | None:
        """Select an agent for the given product + supplier combo.

        Returns the chosen ``agent_id``, or ``None`` if no rule is configured
        (caller should fall back to first‑available logic).
        """
        # 1. Look up routing rule
        row = await self._session.execute(
            text(
                "SELECT id, strategy FROM routing_rules "
                "WHERE supplier_id=:sid AND product_id=:pid"
            ).bindparams(sid=supplier_id, pid=product_id)
        )
        rule = row.first()
        if rule is None:
            return None  # no rule configured → caller falls back

        rule_id, strategy_name = rule

        # 2. Fetch enabled rule items (ordered by priority for determinism)
        items = await self._session.execute(
            text(
                "SELECT agent_id, priority, enabled FROM routing_rule_items "
                "WHERE rule_id=:rid AND enabled=TRUE "
                "ORDER BY priority ASC"
            ).bindparams(rid=rule_id)
        )
        agents = items.all()
        if not agents:
            return None  # no enabled agents → caller falls back

        # 3. Delegate to strategy
        strategy = _STRATEGY_MAP.get(strategy_name)
        if strategy is None:
            # Unknown strategy → fall back
            return None

        return await strategy.select_agent(self._session, agents, product_id)
