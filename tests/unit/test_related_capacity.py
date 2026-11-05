"""Список близких: двое без Premium и десять с действующим Premium."""

from pathlib import Path
from uuid import UUID

from starflow.domain.plans import load_plans
from starflow.domain.quota import LimitReached
from starflow.domain.records import IdempotencyRecord
from starflow.services.quota import QuotaService, StoredResult

USER = UUID(int=1)
ROOT = Path(__file__).resolve().parents[2]


class _Work:
    def __init__(self, store: object) -> None:
        self._store = store

    async def __aenter__(self) -> object:
        return self._store

    async def __aexit__(self, *_args: object) -> None:
        return None


class _People:
    def __init__(self, count: int) -> None:
        self.count = count

    async def count_for_owner(self, _user_id: UUID) -> int:
        return self.count


class _Subs:
    def __init__(self, active: bool) -> None:
        self.active = active

    async def has_active(self, _user_id: UUID, _now: object) -> bool:
        return self.active


class _Keys:
    def __init__(self) -> None:
        self.record: IdempotencyRecord | None = None

    async def lock(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        return self.record

    async def count_reserved(self, _user_id: UUID, _feature: str) -> int:
        return 0

    async def hold(
        self,
        user_id: UUID,
        key: str,
        feature: str,
        marker: dict[str, object],
        _existing: IdempotencyRecord | None,
    ) -> None:
        self.record = IdempotencyRecord(UUID(int=4), user_id, key, feature, "reserved", marker)

    async def complete(self, record_id: UUID, body: dict[str, object]) -> None:
        self.record = IdempotencyRecord(
            record_id,
            USER,
            "kept",
            "related_profile",
            "committed",
            body,
        )


class _Users:
    async def lock(self, _user_id: UUID) -> None:
        return None


class _Store:
    def __init__(self, count: int, *, premium: bool) -> None:
        self.related_profiles = _People(count)
        self.subscriptions = _Subs(premium)
        self.idempotency = _Keys()
        self.users = _Users()
        self.produced = 0

    async def commit(self) -> None:
        return None


def _service(store: _Store) -> QuotaService:
    plans = load_plans(ROOT / "resources" / "plans.yaml", price_stars=250)
    return QuotaService(lambda: _Work(store), plans)


async def _save(store: _Store) -> object:
    service = _service(store)

    async def producer(_uow: object) -> dict[str, object]:
        store.produced += 1
        return {"related_id": "new"}

    return await service.execute(USER, "related_profile", "related-save-1", producer)


async def test_two_close_people_fill_the_free_list() -> None:
    stored = await _save(_Store(1, premium=False))
    assert isinstance(stored, StoredResult)
    blocked = _Store(2, premium=False)
    result = await _save(blocked)
    assert isinstance(result, LimitReached)
    assert blocked.produced == 0


async def test_premium_keeps_room_until_ten_close_people() -> None:
    room = await _save(_Store(9, premium=True))
    assert isinstance(room, StoredResult)
    blocked = _Store(10, premium=True)
    result = await _save(blocked)
    assert isinstance(result, LimitReached)
    assert blocked.produced == 0
