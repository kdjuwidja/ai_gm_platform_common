"""Short exclusive leases (cms_leases for an authoring-service's Campaigns, a
module's own otherwise), so a job that every process of a service schedules
(purge) runs in only one of them at a time, across workers and nodes. MongoDB, which they all share, is the referee."""
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LeaseStore:
    def __init__(self, db, collection: str = "cms_leases") -> None:
        # Each module leases in its own database (Campaigns: cms_leases).
        self._leases = db[collection]

    async def acquire(self, name: str, holder: str, ttl: timedelta) -> bool:
        """Takes the lease if it's free or expired (or already ours), in one
        atomic write. A crashed holder's lease simply expires."""
        now = _now()
        try:
            await self._leases.update_one(
                {"_id": name, "$or": [{"expires_at": {"$lt": now}}, {"holder": holder}]},
                {"$set": {"holder": holder, "expires_at": now + ttl}},
                upsert=True,
            )
            return True
        except DuplicateKeyError:
            # The lease exists and someone else holds it: the filter missed,
            # and the upsert collided with the existing _id.
            return False

    async def release(self, name: str, holder: str) -> None:
        await self._leases.delete_one({"_id": name, "holder": holder})
