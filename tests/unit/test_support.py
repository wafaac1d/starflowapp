"""Тесты обращений в поддержку и закрытия администратором."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from starflow.domain.errors import FieldInvalid
from starflow.domain.support import (
    SupportTicket,
    support_message_ok,
    support_subject_ok,
)
from starflow.services.support import SupportService

MOMENT = datetime(2026, 10, 29, 12, tzinfo=UTC)
USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class _SupportRepo:
    def __init__(self) -> None:
        self.tickets: dict[UUID, SupportTicket] = {}

    async def create(
        self,
        user_id: UUID,
        subject: str,
        message: str,
        now: datetime,
    ) -> UUID:
        ticket_id = UUID(int=len(self.tickets) + 1)
        self.tickets[ticket_id] = SupportTicket(
            id=ticket_id,
            user_id=user_id,
            telegram_id=123456,
            username="testuser",
            display_name="Тест",
            subject=subject,
            message=message,
            status="open",
            created_at=now,
            closed_at=None,
        )
        return ticket_id

    async def list_all(self, limit: int = 100) -> list[SupportTicket]:
        return list(self.tickets.values())[:limit]

    async def close(self, ticket_id: UUID, now: datetime) -> bool:
        ticket = self.tickets.get(ticket_id)
        if ticket is None or ticket.status == "closed":
            return False
        self.tickets[ticket_id] = SupportTicket(
            id=ticket.id,
            user_id=ticket.user_id,
            telegram_id=ticket.telegram_id,
            username=ticket.username,
            display_name=ticket.display_name,
            subject=ticket.subject,
            message=ticket.message,
            status="closed",
            created_at=ticket.created_at,
            closed_at=now,
        )
        return True

    async def get(self, ticket_id: UUID) -> SupportTicket | None:
        return self.tickets.get(ticket_id)


class _Work:
    def __init__(self, repo: _SupportRepo) -> None:
        self.support = repo

    async def __aenter__(self) -> "_Work":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None


def test_validation_rules() -> None:
    assert support_subject_ok("Вопрос по оплате") is True
    assert support_subject_ok("a") is False
    assert support_subject_ok("x" * 101) is False
    assert support_subject_ok("Вопрос 🌟") is False

    assert support_message_ok("Не проходит оплата в боте.") is True
    assert support_message_ok("мал") is False
    assert support_message_ok("x" * 2001) is False
    assert support_message_ok("Привет ✨ как дела") is False


@pytest.mark.asyncio
async def test_create_and_admin_close_ticket() -> None:
    repo = _SupportRepo()
    service = SupportService(lambda: _Work(repo), clock=lambda: MOMENT)

    # 1. User creates ticket
    ticket = await service.create_ticket(
        USER_ID,
        "Вопрос по карте",
        "Не отображаются дома в натальной карте.",
    )
    assert ticket.subject == "Вопрос по карте"
    assert ticket.message == "Не отображаются дома в натальной карте."
    assert ticket.status == "open"

    # 2. Non-admin cannot list tickets
    with pytest.raises(FieldInvalid):
        await service.admin_list_tickets(is_admin=False)

    # 3. Admin lists tickets
    admin_list = await service.admin_list_tickets(is_admin=True)
    assert len(admin_list) == 1
    assert admin_list[0].id == ticket.id
    assert admin_list[0].status == "open"

    # 4. Non-admin cannot close ticket
    with pytest.raises(FieldInvalid):
        await service.admin_close_ticket(is_admin=False, ticket_id=ticket.id)

    # 5. Admin closes ticket
    closed = await service.admin_close_ticket(is_admin=True, ticket_id=ticket.id)
    assert closed is True

    # 6. Ticket is now closed
    closed_list = await service.admin_list_tickets(is_admin=True)
    assert closed_list[0].status == "closed"
    assert closed_list[0].closed_at == MOMENT

    # Closing again returns False
    again = await service.admin_close_ticket(is_admin=True, ticket_id=ticket.id)
    assert again is False
