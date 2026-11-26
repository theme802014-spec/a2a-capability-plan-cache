import asyncio

from capability_plan_cache import PlanStore, SupplyRefresher
from test_lifecycle import supply


def test_parallel_shared_refresh_and_config_change(tmp_path):
    async def run():
        store = PlanStore(tmp_path / "refresh.db")
        both_started = asyncio.Event()
        calls = []

        async def fetch(domain, endpoint):
            calls.append((domain, endpoint))
            if len(calls) >= 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 1)
            return supply(domain)

        refresher = SupplyRefresher(store, fetch)
        endpoints = {"health": "synthetic-health", "community": "synthetic-community"}
        reports = await asyncio.gather(*(refresher.refresh(endpoints) for _ in range(8)))
        assert len(calls) == 2
        assert sum(r["refreshed"] for r in reports) == 1
        await refresher.refresh(endpoints, context_id="credentials-revision-2")
        assert len(calls) == 4
        await refresher.refresh({**endpoints, "health": "synthetic-new"}, context_id="credentials-revision-2")
        assert len(calls) == 6
    asyncio.run(run())


def test_wall_clock_timeout_isolated_failure_and_no_error_message(tmp_path):
    async def run():
        store = PlanStore(tmp_path / "timeout.db")
        async def fetch(domain, endpoint):
            if domain == "health":
                await asyncio.Event().wait()
            if domain == "broken":
                raise RuntimeError("private-URL-and-credential-value")
            return supply(domain)
        refresher = SupplyRefresher(store, fetch, timeout=0.02)
        report = await refresher.refresh({d: "synthetic" for d in ("health", "broken", "community")})
        assert [r["status"] for r in report["events"]] == ["failed", "failed", "ok"]
        assert "private-URL" not in str(report)
        assert store.snapshot()["health"]["refresh_status"] == "failed"
        assert store.snapshot()["community"]["refresh_status"] == "ok"
    asyncio.run(run())
