from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from longscrape_core import JobLease, JobRef, Lease


class RedisJobQueue:
    """Redis-backed lease queue.

    Leases are stored in a sorted set by expiry. Expired leases are reclaimed
    before each claim; settlement is token-bound to prevent stale workers from
    acknowledging a later claim.
    """

    def __init__(
        self,
        url: str,
        *,
        namespace: str = "longscrape",
        lease_duration: timedelta = timedelta(minutes=5),
    ) -> None:
        if lease_duration <= timedelta():
            raise ValueError("lease_duration must be greater than zero")
        try:
            from redis.asyncio import Redis  # type: ignore[import-not-found]
        except ImportError as error:
            raise ImportError(
                "Install longscrape[redis] to use RedisJobQueue"
            ) from error
        self._redis = Redis.from_url(url, decode_responses=True)
        self._key, self.lease_duration = namespace, lease_duration

    def _pending(self, kind: str) -> str:
        return f"{self._key}:queue:{kind}"

    @property
    def _leases(self) -> str:
        return f"{self._key}:leases"

    def _lease_key(self, token: str) -> str:
        return f"{self._key}:lease:{token}"

    async def enqueue(self, ref: JobRef, *, kind: str) -> bool:
        added = await self._redis.sadd(f"{self._key}:enqueued", ref.value)
        if not added:
            return False
        await self._redis.rpush(self._pending(kind), ref.value)
        await self._redis.hset(f"{self._key}:kinds", ref.value, kind)
        return True

    async def _reclaim(self) -> None:
        now = datetime.now(UTC).timestamp()
        tokens = cast(
            list[str], await self._redis.zrangebyscore(self._leases, "-inf", now)
        )
        for token in tokens:
            values = cast(
                dict[str, str], await self._redis.hgetall(self._lease_key(token))
            )
            if values and await self._redis.zrem(self._leases, token):
                await self._redis.rpush(self._pending(values["kind"]), values["ref"])
            await self._redis.delete(self._lease_key(token))

    async def lease(
        self, kind: str, *, duration: timedelta | None = None
    ) -> Lease | None:
        if not kind.strip():
            raise ValueError("kind must not be blank")
        await self._reclaim()
        ref = cast(str | None, await self._redis.lpop(self._pending(kind)))
        if ref is None:
            return None
        duration = duration or self.lease_duration
        if duration <= timedelta():
            raise ValueError("duration must be greater than zero")
        token, expires_at = str(uuid4()), datetime.now(UTC) + duration
        await self._redis.hset(
            self._lease_key(token), mapping={"ref": ref, "kind": kind}
        )
        await self._redis.zadd(self._leases, {token: expires_at.timestamp()})
        return Lease(JobRef(ref), token, expires_at)

    async def _active(self, lease: Lease) -> dict[str, str]:
        await self._reclaim()
        values = cast(
            dict[str, str], await self._redis.hgetall(self._lease_key(lease.token))
        )
        if not values or values.get("ref") != lease.ref.value:
            raise ValueError("Lease is invalid, already settled, or expired")
        return values

    async def acknowledge(self, lease: JobLease) -> None:
        if not isinstance(lease, Lease):
            raise ValueError("Lease was not issued by this queue")
        await self._active(lease)
        await self._redis.zrem(self._leases, lease.token)
        await self._redis.delete(self._lease_key(lease.token))

    async def retry(self, lease: JobLease) -> None:
        if not isinstance(lease, Lease):
            raise ValueError("Lease was not issued by this queue")
        values = await self._active(lease)
        await self.acknowledge(lease)
        await self._redis.rpush(self._pending(values["kind"]), values["ref"])

    async def extend(self, lease: JobLease, *, duration: timedelta) -> Lease:
        if not isinstance(lease, Lease):
            raise ValueError("Lease was not issued by this queue")
        if duration <= timedelta():
            raise ValueError("duration must be greater than zero")
        await self._active(lease)
        expires_at = datetime.now(UTC) + duration
        await self._redis.zadd(self._leases, {lease.token: expires_at.timestamp()})
        return Lease(lease.ref, lease.token, expires_at)

    async def close(self) -> None:
        await self._redis.aclose()

    async def is_empty(self) -> bool:
        await self._reclaim()
        kinds = await self._redis.hvals(f"{self._key}:kinds")
        for kind in kinds:
            if await self._redis.llen(self._pending(cast(str, kind))):
                return False
        return not await self._redis.zcard(self._leases)
