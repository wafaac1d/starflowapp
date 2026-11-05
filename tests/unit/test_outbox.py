from uuid import uuid4

from starflow.domain.records import OutboxJob
from starflow.services.outbox import digest_batches


def _job(telegram_id: int, kind: str) -> OutboxJob:
    return OutboxJob(id=uuid4(), telegram_id=telegram_id, text_key=f"bot.{kind}_ready", kind=kind)


def test_digest_notices_for_one_person_share_a_message() -> None:
    day = _job(7, "day")
    moon = _job(7, "moon")
    other = _job(8, "day")
    nudge = _job(7, "onboarding")
    batches = digest_batches([moon, other, nudge, day])
    assert batches[0] == [day, moon]
    assert batches[1] == [other]
    assert batches[2] == [nudge]
