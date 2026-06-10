from __future__ import annotations

import time


class SnowflakeIDGenerator:
    """Snowflake-style unique ID generator.

    | 1 bit reserved | 41 bits timestamp (ms) | 5 bits datacenter |
    5 bits worker | 12 bits sequence
    """

    EPOCH: int = 1700000000000  # Custom epoch (2023-11-14)

    def __init__(self, worker_id: int = 1, datacenter_id: int = 1) -> None:
        self.worker_id = worker_id & 0x1F
        self.datacenter_id = datacenter_id & 0x1F
        self.sequence = 0
        self.last_timestamp = -1

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_ts: int) -> int:
        ts = self._timestamp()
        while ts <= last_ts:
            ts = self._timestamp()
        return ts

    def next_id(self) -> int:
        ts = self._timestamp()
        if ts < self.last_timestamp:
            raise RuntimeError("Clock moved backwards")
        if ts == self.last_timestamp:
            self.sequence = (self.sequence + 1) & 0xFFF
            if self.sequence == 0:
                ts = self._wait_next_ms(self.last_timestamp)
        else:
            self.sequence = 0
        self.last_timestamp = ts
        return (
            ((ts - self.EPOCH) << 22)
            | (self.datacenter_id << 17)
            | (self.worker_id << 12)
            | self.sequence
        )


# Module-level singleton
id_generator = SnowflakeIDGenerator()
