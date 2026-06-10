from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Each agent row from routing_rule_items: (agent_id, priority, enabled)
AgentRow = tuple[int, int, bool]


class RoutingStrategy(ABC):
    """Abstract routing strategy for selecting an agent."""

    @abstractmethod
    async def select_agent(
        self,
        session: AsyncSession,
        agents: Sequence[AgentRow],
        product_id: int,
    ) -> int | None:
        """Pick one agent_id from the list, or None if none suitable."""
        ...


class RoundRobinStrategy(RoutingStrategy):
    """Round‑robin: assign to the agent with the fewest orders for this product."""

    async def select_agent(
        self,
        session: AsyncSession,
        agents: Sequence[AgentRow],
        product_id: int,
    ) -> int | None:
        if not agents:
            return None

        agent_ids = [a[0] for a in agents]
        placeholders = ",".join(str(aid) for aid in agent_ids)

        # Count existing orders per agent for this product (exclude FAILED/CANCELLED)
        result = await session.execute(
            text(
                f"SELECT agent_id, COUNT(*) AS cnt "
                f"FROM orders "
                f"WHERE product_id=:pid AND agent_id IN ({placeholders}) "
                f"AND status NOT IN ('FAILED','CANCELLED') "
                f"GROUP BY agent_id"
            ).bindparams(pid=product_id)
        )
        counts = dict(result.all())  # {agent_id: count}

        # Find the agent with the smallest count (tie-break by original order)
        best = None
        best_count: int | None = None
        for aid, priority, enabled in agents:
            if not enabled:
                continue
            cnt = counts.get(aid, 0)
            if best is None or cnt < best_count:
                best = aid
                best_count = cnt
        return best


class PriorityStrategy(RoutingStrategy):
    """Priority: return the first enabled agent that has inventory."""

    async def select_agent(
        self,
        session: AsyncSession,
        agents: Sequence[AgentRow],
        product_id: int,
    ) -> int | None:
        if not agents:
            return None

        for aid, priority, enabled in agents:
            if not enabled:
                continue
            # Check inventory
            row = await session.execute(
                text(
                    "SELECT COUNT(*) FROM inventory_items "
                    "WHERE product_id=:pid AND agent_id=:aid AND status='AVAILABLE'"
                ).bindparams(pid=product_id, aid=aid)
            )
            if row.scalar() > 0:
                return aid
        return None


class WeightedStrategy(RoutingStrategy):
    """Weighted: compare expected vs actual distribution, pick the most under‑allocated agent.

    The ``priority`` column is treated as the weight value.
    """

    async def select_agent(
        self,
        session: AsyncSession,
        agents: Sequence[AgentRow],
        product_id: int,
    ) -> int | None:
        if not agents:
            return None

        enabled = [(aid, pri) for aid, pri, en in agents if en]
        if not enabled:
            return None

        total_weight = sum(pri for _, pri in enabled)

        agent_ids = [aid for aid, _ in enabled]
        placeholders = ",".join(str(aid) for aid in agent_ids)

        # Actual order counts per agent for this product
        result = await session.execute(
            text(
                f"SELECT agent_id, COUNT(*) AS cnt "
                f"FROM orders "
                f"WHERE product_id=:pid AND agent_id IN ({placeholders}) "
                f"AND status NOT IN ('FAILED','CANCELLED') "
                f"GROUP BY agent_id"
            ).bindparams(pid=product_id)
        )
        actual_counts = dict(result.all())  # {agent_id: count}
        total_actual = sum(actual_counts.values()) or 1  # avoid div by zero

        # Compute deviation = expected_ratio - actual_ratio
        # Pick the agent with the largest positive deviation (most under-allocated)
        best = None
        best_deviation: float | None = None
        for aid, weight in enabled:
            expected_ratio = weight / total_weight
            actual_ratio = actual_counts.get(aid, 0) / total_actual
            deviation = expected_ratio - actual_ratio
            if best is None or deviation > best_deviation:
                best = aid
                best_deviation = deviation
        return best
