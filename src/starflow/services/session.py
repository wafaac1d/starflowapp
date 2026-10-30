import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID

from starflow.domain.records import User
from starflow.domain.start_param import normalize_start_param
from starflow.domain.time import now_utc
from starflow.repositories.protocols import UserRepository
from starflow.repositories.sql import AuthSessionRepository


@dataclass(frozen=True)
class SessionView:
    user_id: UUID
    telegram_id: int
    username: str | None
    is_admin: bool


@dataclass(frozen=True)
class IssuedSession:
    token: str
    view: SessionView


class SessionStore(Protocol):
    users: UserRepository
    sessions: AuthSessionRepository

    async def commit(self) -> None: ...


class SessionWork(Protocol):
    async def __aenter__(self) -> SessionStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class SessionService:
    def __init__(
        self,
        uow_factory: Callable[[], SessionWork],
        admin_ids: frozenset[int],
        ttl_sec: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._admin_ids = admin_ids
        self._ttl_sec = ttl_sec

    async def accept_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
        language_code: str | None,
        start_param: str | None = None,
    ) -> SessionView:
        async with self._uow_factory() as uow:
            user = await uow.users.upsert_telegram(telegram_id, username, language_code)
            await _remember(uow, user.id, start_param)
            await uow.commit()
        return _view(user, telegram_id in self._admin_ids)

    async def mark_bot_welcomed(self, telegram_id: int) -> bool:
        async with self._uow_factory() as uow:
            is_first = await uow.users.mark_bot_welcomed(telegram_id)
            await uow.commit()
            return is_first

    async def issue(self, view: SessionView) -> IssuedSession:
        token = secrets.token_urlsafe(32)
        expires_at = now_utc() + timedelta(seconds=self._ttl_sec)
        async with self._uow_factory() as uow:
            await uow.sessions.add(view.user_id, _hash_token(token), expires_at)
            await uow.commit()
        return IssuedSession(token, view)

    async def resume(self, token: str) -> SessionView | None:
        if not token:
            return None
        async with self._uow_factory() as uow:
            user = await uow.sessions.find_user(_hash_token(token), now_utc())
        if user is None:
            return None
        return _view(user, user.telegram_id in self._admin_ids)

    async def logout(self, token: str) -> None:
        if not token:
            return
        async with self._uow_factory() as uow:
            await uow.sessions.revoke(_hash_token(token), now_utc())
            await uow.commit()

    async def delete_account(self, user_id: UUID) -> None:
        async with self._uow_factory() as uow:
            await uow.users.delete(user_id)
            await uow.commit()

    async def delete_telegram_account(self, telegram_id: int) -> bool:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_telegram_id(telegram_id)
            if user is None:
                return False
            await uow.users.delete(user.id)
            await uow.commit()
        return True

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self._admin_ids


async def _remember(uow: SessionStore, user_id: UUID, start_param: str | None) -> None:
    normalized = normalize_start_param(start_param)
    if normalized is None:
        return
    await uow.users.remember_start_param(user_id, normalized)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _view(user: User, is_admin: bool) -> SessionView:
    return SessionView(
        user_id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        is_admin=is_admin,
    )
