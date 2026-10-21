"""Бесплатные тексты. Общий кэш не хранит имя и факты рождения конкретного человека."""

import asyncio
import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError

from starflow.ai.catalog import PromptCatalog, PromptSpec
from starflow.ai.client import CircuitOpen, ModelReply
from starflow.ai.guard import guarded_copy
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.quota import LimitReached, QuotaDecision, idempotency_key_ok
from starflow.domain.records import RelatedBirth
from starflow.domain.segments import (
    expires_at,
    facts_text,
    forecast_cache_key,
    moon_segment,
    pair_segment,
    period_key,
    representative_facts,
    sun_segment,
)
from starflow.domain.time import local_date, now_utc
from starflow.i18n.catalog import Catalog
from starflow.repositories.protocols import UserRepository
from starflow.repositories.sql import (
    AiRequestRepository,
    FavoriteRepository,
    ForecastFeedbackRepository,
    ForecastHistoryRepository,
    ProfileRepository,
    RelatedProfileRepository,
)
from starflow.services.quota import QuotaStore, ResultWriter, StoredResult

_KINDS = frozenset({"day", "week", "advice", "moon", "compatibility"})
_REPAIR = (
    "прошлый ответ не подошёл. верни один json-объект со строчными полями title и body, "
    "без emoji и без html."
)


class DraftText(BaseModel):
    title: str
    body: str


@dataclass(frozen=True)
class ReadingView:
    status: str
    title: str | None = None
    body: str | None = None
    greeting: str | None = None
    user_sign: str | None = None
    shared_facts: str | None = None
    history_id: UUID | None = None
    streak: int | None = None
    replayed: bool = False
    reset_at: datetime | None = None


@dataclass
class _Job:
    status: str = "pending"
    view: ReadingView | None = None


class TextModel(Protocol):
    async def complete_forecast(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelReply: ...


class QuotaPort(Protocol):
    async def execute(
        self,
        user_id: UUID,
        feature: str,
        key: str,
        producer: ResultWriter,
    ) -> StoredResult | QuotaDecision: ...


class SkyPort(Protocol):
    async def for_date(self, day: date) -> dict[str, object]: ...


class ForecastStore(Protocol):
    users: UserRepository
    profiles: ProfileRepository
    related_profiles: RelatedProfileRepository
    forecast_history: ForecastHistoryRepository
    favorites: FavoriteRepository
    feedback: ForecastFeedbackRepository
    ai_requests: AiRequestRepository

    async def commit(self) -> None: ...


class ForecastWork(Protocol):
    async def __aenter__(self) -> ForecastStore: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class ForecastService:
    def __init__(
        self,
        uow_factory: Callable[[], ForecastWork],
        cache: TwoLevelCache,
        model: TextModel,
        prompts: PromptCatalog,
        catalog: Catalog,
        quota: QuotaPort,
        sky: SkyPort,
        *,
        fast_model: str,
        pro_model: str,
        zone_name: str,
        locale: str,
        mini_app_url: str,
        clock: Callable[[], datetime] | None = None,
        background: bool = True,
    ) -> None:
        self._uow_factory = uow_factory
        self._cache = cache
        self._model = model
        self._prompts = prompts
        self._catalog = catalog
        self._quota = quota
        self._sky = sky
        self._models = {"fast": fast_model, "pro": pro_model}
        self._zone_name = zone_name
        self._locale = locale
        self._mini_app_url = mini_app_url
        self._clock = clock or now_utc
        self._background = background
        self._jobs: dict[tuple[UUID, str, str], _Job] = {}
        self._idempotency: dict[tuple[UUID, str], tuple[UUID, str, str]] = {}
        self._background_keys: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, user_id: UUID, kind: str, idempotency_key: str) -> ReadingView:
        self._check_kind(kind)
        if not idempotency_key_ok(idempotency_key):
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        moment = self._clock()
        key = period_key(kind, moment, self._zone_name)
        identity = (user_id, kind, key)
        known = self._idempotency.get((user_id, idempotency_key))
        if known is not None:
            return self._job_view(known)
        current = self._jobs.get(identity)
        if current is not None and current.status != "error":
            self._idempotency[(user_id, idempotency_key)] = identity
            return current.view or _pending()
        saved = await self._saved(user_id, kind, _period_day(kind, moment, self._zone_name))
        if saved is not None:
            return saved
        blocked = await self._blocked(user_id, kind)
        if blocked is not None:
            return blocked
        await self.accept_referral(user_id)
        job = _Job()
        self._jobs[identity] = job
        self._idempotency[(user_id, idempotency_key)] = identity
        self._spawn(self._fill(job, user_id, kind, idempotency_key, moment))
        return _pending()

    async def current(self, user_id: UUID, kind: str) -> ReadingView:
        self._check_kind(kind)
        moment = self._clock()
        identity = (user_id, kind, period_key(kind, moment, self._zone_name))
        job = self._jobs.get(identity)
        if job is not None and job.view is not None:
            return job.view
        if job is not None:
            return _pending()
        saved = await self._saved(user_id, kind, _period_day(kind, moment, self._zone_name))
        if saved is not None:
            return saved
        return ReadingView(status="idle")

    async def _fill(
        self,
        job: _Job,
        user_id: UUID,
        kind: str,
        idempotency_key: str,
        moment: datetime,
    ) -> None:
        try:
            if kind == "compatibility":
                view = await self._compatibility(user_id, idempotency_key, moment)
            else:
                view = await self._open(user_id, kind, moment)
        except Exception:
            view = ReadingView(status="error", body=self._catalog.text("errors.reading_failed"))
        job.status = view.status
        job.view = view

    async def _open(self, user_id: UUID, kind: str, moment: datetime) -> ReadingView:
        prepared = await self._prepare(user_id, kind, moment)
        if isinstance(prepared, ReadingView):
            return prepared
        segment, facts, profile = prepared
        payload, shared = await self._shared(user_id, kind, segment, facts, moment)
        if payload.get("source") != "model":
            return self._view(profile, payload, shared, None, None)
        history_id, streak = await self._remember(user_id, kind, moment, payload, profile)
        return self._view(profile, payload, shared, history_id, streak)

    async def _compatibility(
        self,
        user_id: UUID,
        idempotency_key: str,
        moment: datetime,
    ) -> ReadingView:
        prepared = await self._prepare(user_id, "compatibility", moment)
        if isinstance(prepared, ReadingView):
            return prepared
        segment, facts, profile = prepared
        payload, shared = await self._shared(user_id, "compatibility", segment, facts, moment)
        if payload.get("source") != "model":
            return self._view(profile, payload, shared, None, None)
        holder = payload

        async def producer(store: QuotaStore) -> dict[str, object]:
            history_id = await store.forecast_history.add(
                user_id,
                "compatibility",
                _period_day("compatibility", moment, self._zone_name),
                {"title": holder["title"], "body": holder["body"], "source": "model"},
            )
            return {"history_id": str(history_id)}

        result = await self._quota.execute(user_id, "compatibility", idempotency_key, producer)
        if isinstance(result, LimitReached):
            saved = await self._saved(
                user_id,
                "compatibility",
                _period_day("compatibility", moment, self._zone_name),
            )
            if saved is not None:
                return saved
            return ReadingView(status="limit", reset_at=result.reset_at)
        if not isinstance(result, StoredResult):
            return ReadingView(status="premium")
        history_id = UUID(str(result.body["history_id"]))
        return self._view(profile, payload, shared, history_id, None, result.replayed)

    async def _shared(
        self,
        user_id: UUID,
        kind: str,
        segment: str,
        facts: dict[str, object],
        moment: datetime,
    ) -> tuple[dict[str, object], str]:
        prompt = self._prompts.get(kind)
        key = forecast_cache_key(
            kind,
            period_key(kind, moment, self._zone_name),
            segment,
            "",
            self._locale,
            prompt.version,
        )
        shared = facts_text(facts)

        async def produce() -> dict[str, object]:
            payload = await self._model_payload(user_id, kind, facts)
            if payload.get("source") != "model" and self._background:
                self._spawn(
                    self._improve(
                        key, kind, facts, expires_at(kind, moment, self._zone_name), user_id
                    )
                )
            return payload

        hit = await self._cache.get_or_create(
            key, kind, expires_at(kind, moment, self._zone_name), produce
        )
        return hit.payload, shared

    async def _model_payload(
        self,
        user_id: UUID,
        kind: str,
        facts: dict[str, object],
    ) -> dict[str, object]:
        prompt = self._prompts.get(kind)
        model_name = self._models[prompt.tier]
        user = prompt.user.replace("{facts}", facts_text(facts))
        parsed = await self._ask(user_id, kind, model_name, prompt.system, user, prompt)
        if parsed is None:
            parsed = await self._ask(user_id, kind, model_name, prompt.system, _REPAIR, prompt)
        if parsed is None:
            return {
                "title": self._catalog.text(f"ui.reading.{kind}"),
                "body": self._catalog.text(f"ui.reading.fallback_{kind}"),
                "source": "fallback",
            }
        title, body = parsed
        return {"title": title, "body": body, "source": "model"}

    async def _ask(
        self,
        user_id: UUID,
        kind: str,
        model_name: str,
        system: str,
        user: str,
        prompt: PromptSpec,
    ) -> tuple[str, str] | None:
        temperature = prompt.temperature
        max_tokens = prompt.max_tokens
        try:
            reply = await self._model.complete_forecast(
                model=model_name,
                system=system,
                user=user,
                temperature=float(temperature),
                max_tokens=int(max_tokens),
                json_mode=True,
            )
        except CircuitOpen:
            await self._log(user_id, model_name, kind, "circuit_open", None, "circuit_open")
            return None
        except Exception as exc:
            await self._log(user_id, model_name, kind, "error", None, type(exc).__name__)
            return None
        await self._log(user_id, reply.model or model_name, kind, "ok", reply, None)
        return _parse_reply(reply.content)

    async def _improve(
        self,
        key: str,
        kind: str,
        facts: dict[str, object],
        expires: datetime,
        user_id: UUID,
    ) -> None:
        if key in self._background_keys:
            return
        self._background_keys.add(key)
        prompt = self._prompts.get(kind)
        model_name = self._models[prompt.tier]
        user = prompt.user.replace("{facts}", facts_text(facts))
        parsed = await self._ask(user_id, kind, model_name, prompt.system, user, prompt)
        if parsed is None:
            return
        title, body = parsed
        await self._cache.remember(
            key,
            kind,
            {"title": title, "body": body, "source": "model"},
            expires,
        )

    async def _prepare(
        self,
        user_id: UUID,
        kind: str,
        moment: datetime,
    ) -> ReadingView | tuple[str, dict[str, object], object]:
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            births = (
                await uow.related_profiles.list_births(user_id) if kind == "compatibility" else ()
            )
        if kind == "moon":
            day = local_date(moment, self._zone_name)
            sky = await self._sky.for_date(day)
            moon = sky.get("moon_sign")
            phase = sky.get("phase_name")
            facts: dict[str, object] = {
                "date": day.isoformat(),
                "moon": moon if isinstance(moon, str) else "unknown",
                "phase": phase if isinstance(phase, str) else "unknown",
            }
            return moon_segment(day), facts, profile
        if profile.birth_date is None:
            return ReadingView(
                status="blocked", body=self._catalog.text("ui.chart.birth_date_missing")
            )
        sign = calendar_sign(profile.birth_date)
        if kind == "compatibility":
            related = next((item for item in births if item.birth_date is not None), None)
            if related is None or related.birth_date is None:
                return ReadingView(
                    status="blocked", body=self._catalog.text("errors.related_required")
                )
            segment = pair_segment(sign, calendar_sign(related.birth_date))
            return segment, representative_facts(kind, segment), profile
        segment = sun_segment(sign)
        return segment, representative_facts(kind, segment), profile

    async def _remember(
        self,
        user_id: UUID,
        kind: str,
        moment: datetime,
        payload: dict[str, object],
        profile: object,
    ) -> tuple[UUID, int | None]:
        day = _period_day(kind, moment, self._zone_name)
        zone = getattr(profile, "timezone", None) or self._zone_name
        try:
            async with self._uow_factory() as uow:
                found = await uow.forecast_history.find(user_id, kind, day)
                if found is None:
                    history_id = await uow.forecast_history.add(user_id, kind, day, payload)
                else:
                    history_id = found[0]
                streak = None
                if kind == "day":
                    streak = await uow.profiles.touch_streak(user_id, local_date(moment, zone))
                await uow.commit()
                return history_id, streak
        except Conflict:
            async with self._uow_factory() as uow:
                found = await uow.forecast_history.find(user_id, kind, day)
            if found is None:
                raise
            return found[0], None

    async def _saved(self, user_id: UUID, kind: str, day: date) -> ReadingView | None:
        async with self._uow_factory() as uow:
            found = await uow.forecast_history.find(user_id, kind, day)
            profile = await uow.profiles.ensure(user_id)
        if found is None:
            return None
        history_id, payload = found
        sign = None if profile.birth_date is None else calendar_sign(profile.birth_date)
        return ReadingView(
            status="ready" if payload.get("source") == "model" else "fallback",
            title=_as_text(payload.get("title")),
            body=_as_text(payload.get("body")),
            greeting=profile.display_name,
            user_sign=sign,
            history_id=history_id,
            streak=profile.streak_count if kind == "day" else None,
            replayed=True,
        )

    async def _blocked(self, user_id: UUID, kind: str) -> ReadingView | None:
        if kind == "moon":
            return None
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
        if profile.birth_date is None:
            return ReadingView(
                status="blocked", body=self._catalog.text("ui.chart.birth_date_missing")
            )
        return None

    def _view(
        self,
        profile: object,
        payload: dict[str, object],
        shared: str,
        history_id: UUID | None,
        streak: int | None,
        replayed: bool = False,
    ) -> ReadingView:
        sign = getattr(profile, "birth_date", None)
        user_sign = None if sign is None else calendar_sign(sign)
        status = "ready" if payload.get("source") == "model" else "fallback"
        return ReadingView(
            status=status,
            title=_as_text(payload.get("title")),
            body=_as_text(payload.get("body")),
            greeting=getattr(profile, "display_name", None),
            user_sign=user_sign,
            shared_facts=shared,
            history_id=history_id,
            streak=streak,
            replayed=replayed,
        )

    async def _log(
        self,
        user_id: UUID,
        model: str,
        kind: str,
        status: str,
        reply: ModelReply | None,
        error_code: str | None,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.ai_requests.add(
                user_id,
                model,
                kind,
                status,
                None if reply is None else reply.prompt_tokens,
                None if reply is None else reply.completion_tokens,
                None if reply is None else reply.latency_ms,
                error_code,
            )
            await uow.commit()

    async def history(self, user_id: UUID) -> tuple[tuple[UUID, str, date, str], ...]:
        async with self._uow_factory() as uow:
            rows = await uow.forecast_history.list_for_user(user_id)
        listed: list[tuple[UUID, str, date, str]] = []
        for row in rows:
            title = row.payload.get("title")
            label = title if isinstance(title, str) else row.kind
            listed.append((row.id, row.kind, row.period_date, label))
        return tuple(listed)

    async def favorites(self, user_id: UUID) -> tuple[tuple[UUID, str], ...]:
        async with self._uow_factory() as uow:
            rows = await uow.favorites.list_for_user(user_id)
            found: list[tuple[UUID, str]] = []
            for row in rows:
                payload = await uow.forecast_history.payload_for(user_id, row.target_id)
                if payload is None:
                    continue
                title = payload.get("title")
                found.append((row.target_id, title if isinstance(title, str) else row.target_type))
        return tuple(found)

    async def feedback(self, user_id: UUID, history_id: UUID, score: int) -> None:
        if score not in {1, 5}:
            raise FieldInvalid("score", "errors.validation")
        async with self._uow_factory() as uow:
            if not await uow.forecast_history.owned(user_id, history_id):
                raise FieldInvalid("forecast", "errors.not_found")
            try:
                await uow.feedback.add(user_id, history_id, score, None)
                await uow.commit()
            except Conflict:
                return

    async def share(self, user_id: UUID, history_id: UUID) -> str:
        async with self._uow_factory() as uow:
            payload = await uow.forecast_history.payload_for(user_id, history_id)
            if payload is None:
                raise FieldInvalid("forecast", "errors.not_found")
            profile = await uow.profiles.ensure(user_id)
        sign = None if profile.birth_date is None else calendar_sign(profile.birth_date)
        title = payload.get("title")
        body = payload.get("body")
        return public_share(
            title if isinstance(title, str) else "",
            body if isinstance(body, str) else "",
            sign,
        )

    async def related(self, user_id: UUID) -> tuple[RelatedBirth, ...]:
        async with self._uow_factory() as uow:
            return await uow.related_profiles.list_births(user_id)

    async def referral(self, user_id: UUID) -> tuple[str, str]:
        async with self._uow_factory() as uow:
            code = await uow.users.ensure_referral_code(user_id)
            await uow.commit()
        return code, referral_link(self._mini_app_url, code)

    async def accept_referral(self, user_id: UUID) -> None:
        async with self._uow_factory() as uow:
            await uow.users.ensure_referral_code(user_id)
            param = await uow.users.start_param(user_id)
            await uow.users.bind_referrer(user_id, param)
            await uow.commit()

    def _check_kind(self, kind: str) -> None:
        if kind not in _KINDS:
            raise FieldInvalid("kind", "errors.not_found")

    def _job_view(self, identity: tuple[UUID, str, str]) -> ReadingView:
        job = self._jobs.get(identity)
        if job is None or job.view is None:
            return _pending()
        return job.view

    def _spawn(self, work: Coroutine[object, object, None]) -> None:
        task: asyncio.Task[None] = asyncio.create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


def public_share(title: str, body: str, sign: str | None) -> str:
    lines = [line for line in (title, body, sign or "") if line]
    return "\n".join(lines)


def referral_link(base: str, code: str) -> str:
    if base.strip() == "":
        return code
    join = "&" if "?" in base else "?"
    return f"{base}{join}startapp=ref_{code}"


def _pending() -> ReadingView:
    return ReadingView(status="pending")


def _period_day(kind: str, moment: datetime, zone_name: str) -> date:
    local = moment.astimezone(ZoneInfo(zone_name)).date()
    if kind in {"week", "compatibility"}:
        return local - timedelta(days=local.weekday())
    return local


def _parse_reply(content: str) -> tuple[str, str] | None:
    try:
        draft = DraftText.model_validate(json.loads(content))
    except (ValidationError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return guarded_copy(draft.title, draft.body)


def _as_text(value: object) -> str | None:
    if not isinstance(value, str) or value == "":
        return None
    return value
