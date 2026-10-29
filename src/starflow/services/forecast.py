"""Бесплатные тексты. Общий кэш не хранит имя и факты рождения конкретного человека."""

import asyncio
import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from types import TracebackType
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError

from starflow.ai.catalog import PromptCatalog, PromptSpec
from starflow.ai.client import CircuitOpen, ModelReply
from starflow.ai.guard import guarded_copy
from starflow.astro.ecliptic import SIGNS
from starflow.cache.two_level import TwoLevelCache
from starflow.domain.astrology import facts_for_longitude
from starflow.domain.calendar_reading import DayMark, accept_calendar, parse_month
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.features import TOPICS
from starflow.domain.quota import (
    Allowed,
    LimitReached,
    PremiumRequired,
    QuotaDecision,
    idempotency_key_ok,
)
from starflow.domain.records import RelatedBirth
from starflow.domain.segments import (
    calendar_segment,
    detail_segment,
    expires_at,
    facts_text,
    forecast_cache_key,
    moon_segment,
    natal_segment,
    pair_segment,
    period_key,
    personal_segment,
    representative_facts,
    sun_segment,
    synastry_segment,
)
from starflow.domain.stars import pair_subject
from starflow.domain.time import local_date, now_utc
from starflow.i18n.catalog import Catalog
from starflow.logging import get_logger
from starflow.repositories.protocols import UserRepository
from starflow.repositories.sql import (
    AiRequestRepository,
    FavoriteRepository,
    ForecastFeedbackRepository,
    ForecastHistoryRepository,
    ProfileRepository,
    RelatedProfileRepository,
)
from starflow.services.chart import ChartView, NatalStars
from starflow.services.quota import QuotaStore, ResultWriter, StoredResult

_OPEN = frozenset({"day", "week", "advice", "moon", "compatibility"})
_PREMIUM = frozenset(
    {
        "today_detail",
        "tomorrow",
        "personal_day",
        "personal_week",
        "personal_month",
        "topics",
        "calendar",
        "synastry",
        "natal",
    }
)
PAIR_FOCUS = {
    "dialog": "диалог двоих: как они говорят и слышат друг друга",
    "emotions": "эмоции двоих: как они переживают близость",
    "values": "общие ориентиры двоих: что им важно вместе",
}
_KINDS = _OPEN | _PREMIUM
_LOG = get_logger("forecast")
_REPAIR = (
    "Прошлый ответ не подошёл. Верни один json-объект с полями title и body, "
    "без emoji и без html. Пиши с заглавной буквы."
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
    days: tuple[DayMark, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReadingScope:
    topic: str = ""
    month: str = ""
    related_id: UUID | None = None
    left_sign: str = ""
    right_sign: str = ""


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


class NatalFacts(Protocol):
    async def read(self, user_id: UUID) -> ChartView: ...


class QuotaPort(Protocol):
    async def preview(self, user_id: UUID, feature: str) -> QuotaDecision: ...

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
        chart: NatalFacts | None = None,
        stars: NatalStars | None = None,
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
        self._chart = chart
        self._stars = stars
        self._jobs: dict[tuple[UUID, str, str], _Job] = {}
        self._answers: dict[tuple[UUID, str], ReadingView] = {}
        self._background_keys: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(
        self,
        user_id: UUID,
        kind: str,
        idempotency_key: str,
        scope: ReadingScope | None = None,
    ) -> ReadingView:
        scope = scope or ReadingScope()
        self._check_kind(kind)
        self._check_scope(kind, scope)
        if not idempotency_key_ok(idempotency_key):
            raise FieldInvalid("idempotency_key", "errors.idempotency_key")
        moment = self._clock()
        storage, day, identity_key = self._slot(kind, moment, scope)
        identity = (user_id, storage, identity_key)
        answered = self._answers.get((user_id, idempotency_key))
        if answered is not None:
            return answered
        current = self._jobs.get(identity)
        if current is not None and current.status == "pending":
            return _pending()
        if current is not None and current.status == "ready" and current.view is not None:
            self._answers[(user_id, idempotency_key)] = current.view
            return current.view
        saved = await self._saved(user_id, storage, day)
        if saved is not None:
            self._answers[(user_id, idempotency_key)] = saved
            return saved
        blocked = await self._blocked(user_id, kind)
        if blocked is not None:
            self._answers[(user_id, idempotency_key)] = blocked
            return blocked
        await self.accept_referral(user_id)
        job = _Job()
        self._jobs[identity] = job
        self._spawn(self._fill(job, user_id, kind, idempotency_key, moment, scope))
        return _pending()

    async def current(
        self,
        user_id: UUID,
        kind: str,
        scope: ReadingScope | None = None,
    ) -> ReadingView:
        scope = scope or ReadingScope()
        self._check_kind(kind)
        self._check_scope(kind, scope)
        moment = self._clock()
        storage, day, identity_key = self._slot(kind, moment, scope)
        identity = (user_id, storage, identity_key)
        job = self._jobs.get(identity)
        if job is not None and job.view is not None:
            return job.view
        if job is not None:
            return _pending()
        saved = await self._saved(user_id, storage, day)
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
        scope: ReadingScope,
    ) -> None:
        try:
            if kind in _PREMIUM:
                view = await self._premium(user_id, kind, moment, scope)
            elif kind == "compatibility":
                view = await self._compatibility(user_id, idempotency_key, moment)
            else:
                view = await self._open(user_id, kind, moment)
        except Exception:
            view = ReadingView(status="error", body=self._catalog.text("errors.reading_failed"))
        job.status = view.status
        job.view = view
        self._answers[(user_id, idempotency_key)] = view

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
        *,
        topic: str = "",
    ) -> tuple[dict[str, object], str]:
        prompt = self._prompts.get(kind)
        key = forecast_cache_key(
            kind,
            period_key(kind, moment, self._zone_name),
            segment,
            topic,
            self._locale,
            prompt.version,
        )
        shared = facts_text(facts)

        async def produce() -> dict[str, object]:
            payload = await self._model_payload(user_id, kind, facts)
            if payload.get("source") != "model" and self._background:
                improved = await self._improve(
                    key, kind, facts, expires_at(kind, moment, self._zone_name), user_id
                )
                if improved is not None:
                    return improved
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
            _LOG.warning("reading_uses_fallback", kind=kind, model=model_name)
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
        parsed = _parse_reply(reply.content)
        if parsed is None:
            _LOG.warning("model_reply_rejected", kind=kind, model=reply.model or model_name)
        return parsed

    async def _improve(
        self,
        key: str,
        kind: str,
        facts: dict[str, object],
        expires: datetime,
        user_id: UUID,
    ) -> dict[str, object] | None:
        if key in self._background_keys:
            return None
        self._background_keys.add(key)
        try:
            prompt = self._prompts.get(kind)
            model_name = self._models[prompt.tier]
            user = prompt.user.replace("{facts}", facts_text(facts))
            parsed = await self._ask(user_id, kind, model_name, prompt.system, user, prompt)
            if parsed is None:
                return None
            title, body = parsed
            payload: dict[str, object] = {"title": title, "body": body, "source": "model"}
            await self._cache.remember(key, kind, payload, expires)
            return payload
        finally:
            self._background_keys.discard(key)

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
        *,
        day: date | None = None,
    ) -> tuple[UUID, int | None]:
        day = _period_day(kind, moment, self._zone_name) if day is None else day
        zone = getattr(profile, "timezone", None) or self._zone_name
        version = self._prompt_version(kind)
        stored = dict(payload)
        if version is not None:
            stored["prompt_version"] = version
        payload = stored
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
            days=_marks(payload.get("days")),
            limitations=_texts(payload.get("limitations")),
        )

    async def _blocked(self, user_id: UUID, kind: str) -> ReadingView | None:
        if kind in {"moon", "today_detail", "tomorrow"}:
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
        limitations: tuple[str, ...] = (),
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
            days=_marks(payload.get("days")),
            limitations=limitations or _texts(payload.get("limitations")),
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

    async def open_favorite(self, user_id: UUID, history_id: UUID) -> tuple[str, str]:
        async with self._uow_factory() as uow:
            rows = await uow.favorites.list_for_user(user_id)
            kept = any(
                row.target_id == history_id and row.target_type == "forecast" for row in rows
            )
            payload = await uow.forecast_history.payload_for(user_id, history_id) if kept else None
        if payload is None:
            raise FieldInvalid("forecast", "errors.not_found")
        body = payload.get("body")
        if not isinstance(body, str) or body.strip() == "":
            raise FieldInvalid("forecast", "errors.not_found")
        title = payload.get("title")
        label = title.strip() if isinstance(title, str) and title.strip() != "" else "Прогноз"
        return label, body

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

    async def allow_related(self, user_id: UUID, related_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            allowed = await uow.related_profiles.set_consent(user_id, related_id, True)
            if allowed:
                await uow.commit()
            return allowed

    async def delete_related(self, user_id: UUID, related_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            deleted = await uow.related_profiles.delete_owned(user_id, related_id)
            if deleted:
                await uow.commit()
            return deleted

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

    async def _premium(
        self,
        user_id: UUID,
        kind: str,
        moment: datetime,
        scope: ReadingScope,
    ) -> ReadingView:
        decision = await self._quota.preview(user_id, kind)
        if isinstance(decision, PremiumRequired):
            if await self._unlocked(user_id, kind, scope):
                decision = Allowed()
            elif kind in {"synastry", "natal"} and self._stars is not None:
                return ReadingView(status="stars", body=self._catalog.text("errors.stars_required"))
            else:
                return ReadingView(status="premium", body=self._catalog.text("ui.paywall.lead"))
        if not isinstance(decision, Allowed):
            reset = decision.reset_at if isinstance(decision, LimitReached) else None
            return ReadingView(status="limit", reset_at=reset)
        prepared = await self._prepare_premium(user_id, kind, moment, scope)
        if isinstance(prepared, ReadingView):
            return prepared
        segment, facts, profile, limitations, storage, day, when = prepared
        if kind == "calendar":
            payload, shared = await self._calendar_text(user_id, segment, facts, when, scope)
        else:
            payload, shared = await self._shared(
                user_id, kind, segment, facts, when, topic=scope.topic
            )
        payload = _with_limits(payload, limitations, self._catalog)
        if payload.get("source") != "model":
            return self._view(profile, payload, shared, None, None, limitations=limitations)
        history_id, streak = await self._remember(user_id, storage, when, payload, profile, day=day)
        return self._view(
            profile,
            payload,
            shared,
            history_id,
            streak,
            limitations=limitations,
        )

    async def _unlocked(self, user_id: UUID, kind: str, scope: ReadingScope) -> bool:
        stars = self._stars
        if stars is None:
            return False
        if kind == "natal":
            return await stars.owns(user_id, "natal", "self")
        if kind != "synastry":
            return False
        if scope.left_sign != "" and scope.right_sign != "":
            try:
                subject = pair_subject(scope.left_sign, scope.right_sign)
            except ValueError:
                return False
            return await stars.owns(user_id, "compatibility", subject)
        if scope.related_id is not None:
            return await stars.owns(user_id, "compatibility", f"related:{scope.related_id}")
        return False

    async def _prepare_premium(
        self,
        user_id: UUID,
        kind: str,
        moment: datetime,
        scope: ReadingScope,
    ) -> ReadingView | tuple[str, dict[str, object], object, tuple[str, ...], str, date, datetime]:
        storage, day, _identity = self._slot(kind, moment, scope)
        when = _scoped_moment(kind, moment, self._zone_name, scope)
        async with self._uow_factory() as uow:
            profile = await uow.profiles.ensure(user_id)
            related = None
            if scope.related_id is not None:
                related = await uow.related_profiles.get_owned(user_id, scope.related_id)
        if kind in {"today_detail", "tomorrow"}:
            sky_day = when.astimezone(ZoneInfo(self._zone_name)).date()
            sky = await self._sky.for_date(sky_day)
            segment, facts = _sky_facts(kind, sky, sky_day)
            return segment, facts, profile, (), storage, day, when
        if kind == "synastry" and scope.left_sign != "" and scope.right_sign != "":
            left_sign, right_sign = checked_signs(scope.left_sign, scope.right_sign)
            segment = synastry_segment(
                {"sun": left_sign, "moon": None, "asc": None},
                {"sun": right_sign, "moon": None, "asc": None},
            )
            return (
                segment,
                pair_facts(segment, scope.topic),
                profile,
                (),
                storage,
                day,
                when,
            )
        if profile.birth_date is None:
            return ReadingView(
                status="blocked", body=self._catalog.text("ui.chart.birth_date_missing")
            )
        sign = calendar_sign(profile.birth_date)
        moon, ascendant = await self._natal_signs(user_id)
        if kind == "natal":
            return await self._natal_prepared(user_id, profile, storage, day, when)
        if kind == "synastry":
            if related is None or related.birth_date is None:
                return ReadingView(
                    status="blocked", body=self._catalog.text("errors.related_required")
                )
            if not related.consent:
                return ReadingView(
                    status="blocked", body=self._catalog.text("errors.consent_required")
                )
            left = {"sun": sign, "moon": moon, "asc": ascendant}
            right = {
                "sun": calendar_sign(related.birth_date),
                "moon": None,
                "asc": None,
            }
            segment = synastry_segment(left, right)
            limitations = _synastry_limits(profile, related)
            return (
                segment,
                pair_facts(segment, scope.topic),
                profile,
                limitations,
                storage,
                day,
                when,
            )
        if kind == "calendar":
            sky = await self._sky.for_date(day)
            sky_moon = sky.get("moon_sign")
            moon_sign = sky_moon if isinstance(sky_moon, str) else (moon or "unknown")
            segment = calendar_segment(sign, moon_sign, ascendant, scope.month)
            facts = representative_facts(kind, segment)
            return segment, facts, profile, (), storage, day, when
        segment = personal_segment(sign, moon, ascendant)
        facts = representative_facts(kind, segment)
        if kind == "topics":
            facts = {**facts, "topic": scope.topic}
        return segment, facts, profile, (), storage, day, when

    async def _natal_prepared(
        self,
        user_id: UUID,
        profile: object,
        storage: str,
        day: date,
        when: datetime,
    ) -> ReadingView | tuple[str, dict[str, object], object, tuple[str, ...], str, date, datetime]:
        if self._chart is None:
            return ReadingView(status="blocked", body=self._catalog.text("errors.reading_failed"))
        chart = await self._chart.read(user_id)
        if chart.natal_access != "allowed":
            return ReadingView(status="premium", body=self._catalog.text("ui.paywall.lead"))
        houses = () if chart.houses is None else chart.houses
        segment = natal_segment(
            [item.sign or "unknown" for item in chart.planets],
            list(houses),
            list(chart.aspects),
        )
        return segment, natal_facts(chart), profile, (), storage, day, when

    async def _calendar_text(
        self,
        user_id: UUID,
        segment: str,
        facts: dict[str, object],
        moment: datetime,
        scope: ReadingScope,
    ) -> tuple[dict[str, object], str]:
        prompt = self._prompts.get("calendar")
        key = forecast_cache_key(
            "calendar",
            scope.month,
            segment,
            "",
            self._locale,
            prompt.version,
        )

        async def produce() -> dict[str, object]:
            return await self._calendar_payload(user_id, facts, scope)

        hit = await self._cache.get_or_create(
            key, "calendar", expires_at("calendar", moment, self._zone_name), produce
        )
        return hit.payload, facts_text(facts)

    async def _calendar_payload(
        self,
        user_id: UUID,
        facts: dict[str, object],
        scope: ReadingScope,
    ) -> dict[str, object]:
        prompt = self._prompts.get("calendar")
        model_name = self._models[prompt.tier]
        user = prompt.user.replace("{facts}", facts_text(facts))
        year, month = parse_month(scope.month)
        parsed = await self._ask_raw(user_id, "calendar", model_name, prompt.system, user, prompt)
        accepted = None if parsed is None else accept_calendar(year, month, parsed)
        if accepted is None:
            repair = (
                "Прошлый json не покрыл месяц. Верни title и days на каждый день этого месяца, "
                "оценки от 1 до 5, без чужих дат."
            )
            parsed = await self._ask_raw(
                user_id, "calendar", model_name, prompt.system, repair, prompt
            )
            accepted = None if parsed is None else accept_calendar(year, month, parsed)
        if accepted is None:
            _LOG.warning("reading_uses_fallback", kind="calendar", model=model_name)
            return {
                "title": self._catalog.text("ui.reading.calendar"),
                "body": self._catalog.text("ui.reading.fallback_calendar"),
                "source": "fallback",
            }
        title, days = accepted
        return {
            "title": title,
            "body": self._catalog.text("ui.reading.calendar"),
            "days": [
                {"date": mark.day, "scores": dict(mark.scores), "note": mark.note} for mark in days
            ],
            "source": "model",
        }

    async def _ask_raw(
        self,
        user_id: UUID,
        kind: str,
        model_name: str,
        system: str,
        user: str,
        prompt: PromptSpec,
    ) -> object | None:
        try:
            reply = await self._model.complete_forecast(
                model=model_name,
                system=system,
                user=user,
                temperature=float(prompt.temperature),
                max_tokens=int(prompt.max_tokens),
                json_mode=True,
            )
        except CircuitOpen:
            await self._log(user_id, model_name, kind, "circuit_open", None, "circuit_open")
            return None
        except Exception as exc:
            await self._log(user_id, model_name, kind, "error", None, type(exc).__name__)
            return None
        await self._log(user_id, reply.model or model_name, kind, "ok", reply, None)
        try:
            return cast(object, json.loads(reply.content))
        except json.JSONDecodeError:
            _LOG.warning("model_reply_rejected", kind=kind, model=reply.model or model_name)
            return None

    async def _natal_signs(self, user_id: UUID) -> tuple[str | None, str | None]:
        if self._chart is None:
            return None, None
        view = await self._chart.read(user_id)
        if view.natal_access != "allowed":
            return None, None
        return view.moon_sign, view.ascendant_sign

    def _slot(self, kind: str, moment: datetime, scope: ReadingScope) -> tuple[str, date, str]:
        day = _target_day(kind, moment, self._zone_name, scope)
        storage = kind
        if kind == "topics":
            storage = f"topics:{scope.topic}"
        elif kind == "synastry" and scope.left_sign != "" and scope.right_sign != "":
            left_sign, right_sign = checked_signs(scope.left_sign, scope.right_sign)
            storage = f"synastry:{scope.topic}:{left_sign}:{right_sign}"
        elif kind == "synastry" and scope.related_id is not None:
            storage = f"synastry:{scope.related_id}"
            if scope.topic != "":
                storage = f"{storage}:{scope.topic}"
        return storage, day, f"{day.isoformat()}|{scope.topic}|{scope.month}"

    def _check_scope(self, kind: str, scope: ReadingScope) -> None:
        if kind == "topics" and scope.topic not in TOPICS:
            raise FieldInvalid("topic", "errors.validation")
        if kind == "calendar":
            try:
                parse_month(scope.month)
            except ValueError as error:
                raise FieldInvalid("month", "errors.validation") from error
        if kind == "synastry":
            if scope.topic != "" and scope.topic not in PAIR_FOCUS:
                raise FieldInvalid("topic", "errors.validation")
            has_signs = scope.left_sign != "" or scope.right_sign != ""
            if scope.related_id is None and not has_signs:
                raise FieldInvalid("related_id", "errors.related_required")
            if has_signs:
                checked_signs(scope.left_sign, scope.right_sign)

    def _prompt_version(self, kind: str) -> int | None:
        for name in (kind, kind.split(":", 1)[0]):
            try:
                return self._prompts.get(name).version
            except KeyError:
                continue
        return None

    def _check_kind(self, kind: str) -> None:
        if kind not in _KINDS:
            raise FieldInvalid("kind", "errors.not_found")

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


def _target_day(kind: str, moment: datetime, zone_name: str, scope: ReadingScope) -> date:
    local = moment.astimezone(ZoneInfo(zone_name)).date()
    if kind == "tomorrow":
        return local + timedelta(days=1)
    if kind == "calendar":
        year, month = parse_month(scope.month)
        return date(year, month, 1)
    if kind in {"week", "personal_week", "compatibility"}:
        return local - timedelta(days=local.weekday())
    if kind in {"personal_month"}:
        return date(local.year, local.month, 1)
    return local


def _scoped_moment(kind: str, moment: datetime, zone_name: str, scope: ReadingScope) -> datetime:
    zone = ZoneInfo(zone_name)
    if kind == "tomorrow":
        day = _target_day(kind, moment, zone_name, scope)
        return datetime.combine(day, time.min, tzinfo=zone)
    if kind == "calendar":
        year, month = parse_month(scope.month)
        return datetime(year, month, 1, tzinfo=zone)
    return moment


def _sky_facts(kind: str, sky: dict[str, object], day: date) -> tuple[str, dict[str, object]]:
    sun = sky.get("sun_sign")
    moon = sky.get("moon_sign")
    sun_sign = sun if isinstance(sun, str) else "unknown"
    moon_sign = moon if isinstance(moon, str) else "unknown"
    decan = "unknown"
    bodies = sky.get("bodies")
    if isinstance(bodies, list):
        for body in bodies:
            if not isinstance(body, dict) or body.get("name") != "солнце":
                continue
            longitude = body.get("longitude")
            if isinstance(longitude, int | float):
                decan = str(facts_for_longitude(float(longitude)).decan)
    segment = (
        detail_segment(sun_sign, moon_sign, int(decan))
        if decan.isdigit()
        else (f"{sun_sign}+{moon_sign}+unknown")
    )
    facts = representative_facts(kind, segment)
    facts["date"] = day.isoformat()
    return segment, facts


def checked_signs(left: str, right: str) -> tuple[str, str]:
    normalized = (_known_sign(left), _known_sign(right))
    if normalized[0] is None or normalized[1] is None:
        raise FieldInvalid("sign", "errors.validation")
    return normalized[0], normalized[1]


def pair_facts(segment: str, topic: str) -> dict[str, object]:
    facts = representative_facts("synastry", segment)
    focus = PAIR_FOCUS.get(topic, "")
    if focus == "":
        return facts
    return {**facts, "focus": focus}


def natal_facts(chart: ChartView) -> dict[str, object]:
    planets = [{"name": item.name, "sign": item.sign or "unknown"} for item in chart.planets]
    return {
        "sun": chart.sun_sign or "unknown",
        "moon": chart.moon_sign or "unknown",
        "ascendant": chart.ascendant_sign or "unknown",
        "houses": "unknown" if chart.houses is None else list(chart.houses),
        "planets": planets,
        "aspects": list(chart.aspects),
    }


def _known_sign(value: str) -> str | None:
    sign = value.casefold().strip()
    if sign in SIGNS:
        return sign
    return None


def _synastry_limits(profile: object, related: object) -> tuple[str, ...]:
    notes: list[str] = []
    if getattr(profile, "birth_time", None) is None:
        notes.append("owner_time_unknown")
    if getattr(profile, "latitude", None) is None or getattr(profile, "longitude", None) is None:
        notes.append("owner_place_missing")
    if getattr(related, "birth_time_unknown", True):
        notes.append("related_time_unknown")
    if getattr(related, "latitude", None) is None or getattr(related, "longitude", None) is None:
        notes.append("related_place_missing")
    return tuple(notes)


def _with_limits(
    payload: dict[str, object],
    limitations: tuple[str, ...],
    catalog: Catalog,
) -> dict[str, object]:
    if not limitations:
        return payload
    notes = [catalog.text(f"ui.synastry.{code}") for code in limitations]
    body = payload.get("body")
    text = body if isinstance(body, str) else ""
    merged = "\n".join(part for part in (text, *notes) if part)
    return {**payload, "body": merged, "limitations": list(limitations)}


def _marks(value: object) -> tuple[DayMark, ...]:
    if not isinstance(value, list):
        return ()
    marks: list[DayMark] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        day = item.get("date")
        scores = item.get("scores")
        note = item.get("note")
        if not isinstance(day, str) or not isinstance(scores, dict) or not isinstance(note, str):
            continue
        pairs = tuple(
            (key, score)
            for key, score in scores.items()
            if isinstance(key, str) and isinstance(score, int) and not isinstance(score, bool)
        )
        marks.append(DayMark(day, pairs, note))
    return tuple(marks)


def _texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
