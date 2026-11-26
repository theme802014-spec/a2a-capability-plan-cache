"""Concurrent Card refresh with injected I/O and no bundled HTTP credentials."""
from __future__ import annotations

import asyncio
import copy
import math
import time


class SupplyRefresher:
    """One in-flight batch per instance, with independent supplier failures.

    ``fetch(domain, endpoint)`` is async and returns a validated normalized supply.
    ``context_id`` is an opaque caller revision, changed on endpoint/auth changes;
    do not put tokens in it. All normalized snapshots must carry stable source_id.
    """
    def __init__(self, store, fetch, *, interval=60, max_age=120, timeout=5,
                 monotonic=time.monotonic):
        if any(not math.isfinite(v) or v <= 0 for v in (interval, max_age, timeout)):
            raise ValueError("positive finite refresh limits required")
        self.store, self.fetch = store, fetch
        self.interval = min(interval, max_age / 2)
        self.timeout, self.monotonic = timeout, monotonic
        self._lock = asyncio.Lock()
        self._context = None
        self._completed = None

    async def refresh(self, endpoints, *, context_id="default", force=False):
        endpoints = copy.deepcopy(endpoints)
        context = (tuple(sorted(endpoints.items())), context_id)

        def due():
            return (force or self._completed is None or context != self._context
                    or self.monotonic() - self._completed >= self.interval)

        if not due():
            return {"refreshed": False, "events": []}
        async with self._lock:
            if not due():
                return {"refreshed": False, "events": []}
            started = self.monotonic()

            async def one(domain, endpoint):
                try:
                    supply = await asyncio.wait_for(self.fetch(domain, endpoint), self.timeout)
                    if not isinstance(supply.get("source_id"), str) or not supply["source_id"]:
                        raise ValueError("source identity required")
                    await asyncio.to_thread(self.store.observe, domain, supply)
                    return {"domain": domain, "status": "ok"}
                except Exception as exc:
                    await asyncio.to_thread(self.store.observe_failure, domain, type(exc).__name__)
                    return {"domain": domain, "status": "failed", "error_type": type(exc).__name__}

            events = await asyncio.gather(*(one(domain, url) for domain, url in endpoints.items()))
            self._completed, self._context = self.monotonic(), context
            return {"refreshed": True, "events": events,
                    "refresh_ms": (self.monotonic() - started) * 1000}
