"""A job every process of a service schedules but only one runs at a time,
across workers and nodes — the holder of its lease (shared/lease_store.py). Purge, art matching and music upkeep run
this way."""
import asyncio
import logging
import uuid
from datetime import timedelta
from typing import Awaitable, Callable

from shared.lease_store import LeaseStore

logger = logging.getLogger("cms.jobs")


class JobBusy(Exception):
    """Another process holds the job's lease right now."""


class LeasedJob:
    def __init__(self, name: str, run: Callable[[], Awaitable[dict]], leases: LeaseStore,
                 lease_minutes: int, interval_minutes: int) -> None:
        self._name = name
        self._run = run
        self._leases = leases
        self._lease_ttl = timedelta(minutes=lease_minutes)
        self._interval = interval_minutes * 60
        self._holder = uuid.uuid4().hex  # this process
        self._kicked: set[asyncio.Task] = set()

    async def run_now(self) -> dict:
        """Runs the job once while holding its lease; raises JobBusy if
        another process holds it."""
        if not await self._leases.acquire(self._name, self._holder, self._lease_ttl):
            raise JobBusy()
        try:
            return await self._run()
        finally:
            await self._leases.release(self._name, self._holder)

    async def run_forever(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._run_logged()

    def kick(self) -> None:
        """Runs the job soon, in the background, without waiting for its
        schedule. Busy means it's already running somewhere: the schedule
        picks up whatever that run missed."""
        task = asyncio.create_task(self._run_logged())
        self._kicked.add(task)  # held until done, so it isn't garbage-collected
        task.add_done_callback(self._kicked.discard)

    async def _run_logged(self) -> None:
        try:
            await self.run_now()
        except JobBusy:
            pass  # another process has it this round
        except Exception:
            logger.exception("Job %s failed", self._name)
