"""Leases and the jobs that run under them, against a real MongoDB: one
holder at a time, an expired lease free to take, and a busy job skipped.
Skipped unless SHARED_TEST_MONGO_URI points at a throwaway instance; each
test uses its own database and drops it."""
import asyncio
import os
import uuid
from datetime import timedelta

import pytest
from pymongo import AsyncMongoClient

from shared.lease_store import LeaseStore
from shared.leased_job import JobBusy, LeasedJob

MONGO_URI = os.getenv("SHARED_TEST_MONGO_URI")
pytestmark = pytest.mark.skipif(not MONGO_URI, reason="SHARED_TEST_MONGO_URI not set")
MINUTE = timedelta(minutes=1)


def with_leases(test):
    """Runs `test(leases)` on a fresh database, dropped afterwards."""
    async def run():
        mongo = AsyncMongoClient(MONGO_URI, tz_aware=True)
        name = f"shared_{uuid.uuid4().hex[:8]}"
        try:
            await test(LeaseStore(mongo[name], "leases"))
        finally:
            await mongo.drop_database(name)
            await mongo.close()
    asyncio.run(run())


def test_one_holder_at_a_time():
    async def test(leases):
        assert await leases.acquire("purge", "a", MINUTE)
        assert not await leases.acquire("purge", "b", MINUTE)
        assert await leases.acquire("purge", "a", MINUTE)  # already ours
        await leases.release("purge", "b")                  # not b's to release
        assert not await leases.acquire("purge", "b", MINUTE)
        await leases.release("purge", "a")
        assert await leases.acquire("purge", "b", MINUTE)
    with_leases(test)


def test_an_expired_lease_is_free():
    async def test(leases):
        assert await leases.acquire("purge", "a", timedelta(seconds=-1))
        assert await leases.acquire("purge", "b", MINUTE)
    with_leases(test)


def test_a_job_runs_under_its_lease_and_lets_go():
    async def test(leases):
        runs = []

        async def run():
            runs.append(1)
            assert not await leases.acquire("music", "someone-else", MINUTE)
            return {"done": True}

        job = LeasedJob("music", run, leases, lease_minutes=1, interval_minutes=60)
        assert await job.run_now() == {"done": True}
        assert await leases.acquire("music", "someone-else", MINUTE)  # released after the run
        assert runs == [1]
    with_leases(test)


def test_a_busy_job_is_not_run():
    async def test(leases):
        async def run():
            raise AssertionError("must not run")

        assert await leases.acquire("purge", "another-process", MINUTE)
        job = LeasedJob("purge", run, leases, lease_minutes=1, interval_minutes=60)
        with pytest.raises(JobBusy):
            await job.run_now()
    with_leases(test)
