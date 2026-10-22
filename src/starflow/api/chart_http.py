"""Карта, небо и допуск. Проверка paywall ничего не резервирует."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from starflow.api.actor import actor_from_cookie, require_intent
from starflow.api.http import ApiError
from starflow.bootstrap import Container
from starflow.domain.astrology import facts_for_longitude
from starflow.domain.calendar_sign import calendar_sign
from starflow.domain.chart_sections import chart_sections
from starflow.domain.errors import Conflict, FieldInvalid
from starflow.domain.local_time import user_week
from starflow.domain.quota import Allowed, LimitReached, PremiumRequired, QuotaDecision
from starflow.domain.time import local_date, now_utc
from starflow.services.chart import ChartView, PlanetPlacement
from starflow.services.quota import QuotaStore, ResultWriter, StoredResult


class PlanetBody(BaseModel):
    name: str
    longitude: float
    sign: str | None
    element: str | None
    modality: str | None
    ruler: str | None
    decan: int | None
    decan_ruler: str | None
    retrograde: bool
    exact: bool


class SectionBody(BaseModel):
    id: str
    title: str
    body: str


class ChartBody(BaseModel):
    sun_sign: str | None
    sun_sign_source: str
    moon_sign: str | None
    ascendant_sign: str | None
    houses: list[str] | None
    planets: list[PlanetBody]
    aspects: list[str]
    transits: list[str]
    lunar_day: int | None
    phase_name: str | None
    limitations: list[str]
    natal_access: str
    sections: list[SectionBody] = []


class SkyBody(BaseModel):
    sun_sign: str
    moon_sign: str
    phase_name: str
    bodies: list[PlanetBody]


class AccessBody(BaseModel):
    feature: str
    decision: str
    reset_at: datetime | None = None


class FavoriteBody(BaseModel):
    target_id: UUID


class FavoriteResult(BaseModel):
    favorite_id: UUID
    target_id: UUID
    replayed: bool


class CompatibilityResult(BaseModel):
    user_sign: str
    related_sign: str
    related_id: UUID
    history_id: UUID
    replayed: bool


def register_chart_routes(router: APIRouter, container: Container) -> None:
    unauthorized = container.catalog.text("errors.unauthorized")
    not_found = container.catalog.text("errors.not_found")

    @router.get("/chart", response_model=ChartBody)
    async def read_chart(request: Request) -> ChartBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        view = await container.chart_service.read(actor.view.user_id)
        return _chart(view, container.catalog.text)

    @router.get("/sky", response_model=SkyBody)
    async def read_sky(request: Request) -> SkyBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        async with container.uow_factory() as uow:
            profile = await uow.profiles.ensure(actor.view.user_id)
        zone = profile.timezone or container.settings.default_timezone
        payload = await container.sky_service.for_date(local_date(now_utc(), zone))
        return _sky(payload)

    @router.get("/access/{feature}", response_model=AccessBody)
    async def read_access(feature: str, request: Request) -> AccessBody:
        actor = await actor_from_cookie(request, container, unauthorized)
        try:
            container.plans.rule(feature)
        except KeyError as error:
            raise ApiError(404, "not_found", not_found) from error
        try:
            decision = await container.quota_service.preview(actor.view.user_id, feature)
        except FieldInvalid as error:
            raise _field_error(container, error) from error
        return _access(feature, decision)

    @router.post("/favorites", response_model=FavoriteResult)
    async def add_favorite(
        body: FavoriteBody,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> FavoriteResult:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)
        if not await _owns_history(container, actor.view.user_id, body.target_id):
            raise ApiError(404, "not_found", not_found)

        async def producer(store: QuotaStore) -> dict[str, object]:
            return await _favorite(store, actor.view.user_id, body.target_id)

        result = await _run(container, actor.view.user_id, "favorite", idempotency_key, producer)
        return FavoriteResult(
            favorite_id=UUID(_text(result.body, "favorite_id")),
            target_id=UUID(_text(result.body, "target_id")),
            replayed=result.replayed,
        )

    @router.post("/compatibility", response_model=CompatibilityResult)
    async def read_compatibility(
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> CompatibilityResult:
        require_intent(request, unauthorized)
        actor = await actor_from_cookie(request, container, unauthorized)

        async def producer(store: QuotaStore) -> dict[str, object]:
            return await _compatibility(store, actor.view.user_id)

        result = await _run(
            container,
            actor.view.user_id,
            "compatibility",
            idempotency_key,
            producer,
        )
        return CompatibilityResult(
            user_sign=_text(result.body, "user_sign"),
            related_sign=_text(result.body, "related_sign"),
            related_id=UUID(_text(result.body, "related_id")),
            history_id=UUID(_text(result.body, "history_id")),
            replayed=result.replayed,
        )


async def _run(
    container: Container,
    user_id: UUID,
    feature: str,
    key: str,
    producer: ResultWriter,
) -> StoredResult:
    try:
        outcome = await container.quota_service.execute(user_id, feature, key, producer)
    except FieldInvalid as error:
        raise _field_error(container, error) from error
    except Conflict as error:
        raise ApiError(409, "conflict", container.catalog.text("errors.conflict")) from error
    if isinstance(outcome, StoredResult):
        return outcome
    raise _quota_error(container, outcome)


async def _owns_history(container: Container, user_id: UUID, history_id: UUID) -> bool:
    async with container.uow_factory() as uow:
        return await uow.forecast_history.owned(user_id, history_id)


async def _favorite(store: QuotaStore, user_id: UUID, target_id: UUID) -> dict[str, object]:
    favorite_id = await store.favorites.add(user_id, "forecast", target_id)
    return {"favorite_id": str(favorite_id), "target_id": str(target_id)}


async def _compatibility(store: QuotaStore, user_id: UUID) -> dict[str, object]:
    profile = await store.profiles.get_by_user_id(user_id)
    births = await store.related_profiles.list_births(user_id)
    related = next((item for item in births if item.birth_date is not None), None)
    if profile is None or profile.birth_date is None or profile.timezone is None:
        raise FieldInvalid("birth_date", "errors.onboarding_incomplete")
    if related is None or related.birth_date is None:
        raise FieldInvalid("related_profile", "errors.related_required")
    start, _end = user_week(now_utc(), profile.timezone)
    payload: dict[str, object] = {
        "user_sign": calendar_sign(profile.birth_date),
        "related_sign": calendar_sign(related.birth_date),
        "related_id": str(related.id),
    }
    history_id = await store.forecast_history.add(user_id, "compatibility", start.date(), payload)
    payload["history_id"] = str(history_id)
    return payload


def _quota_error(container: Container, decision: QuotaDecision) -> ApiError:
    if isinstance(decision, LimitReached):
        return ApiError(
            429,
            "limit_reached",
            container.catalog.text("errors.limit_reached"),
            reset_at=decision.reset_at,
        )
    if isinstance(decision, PremiumRequired):
        return ApiError(403, "premium_required", container.catalog.text("errors.premium_required"))
    return ApiError(409, "conflict", container.catalog.text("errors.conflict"))


def _field_error(container: Container, error: FieldInvalid) -> ApiError:
    return ApiError(
        422,
        "validation_error",
        container.catalog.text("errors.validation"),
        {error.field: container.catalog.text(error.message_key)},
    )


def _chart(view: ChartView, line: Callable[[str], str]) -> ChartBody:
    return ChartBody(
        sun_sign=view.sun_sign,
        sun_sign_source=view.sun_sign_source,
        moon_sign=view.moon_sign,
        ascendant_sign=view.ascendant_sign,
        houses=None if view.houses is None else list(view.houses),
        planets=[_planet(item) for item in view.planets],
        aspects=list(view.aspects),
        transits=list(view.transits),
        lunar_day=view.lunar_day,
        phase_name=view.phase_name,
        limitations=list(view.limitations),
        natal_access=view.natal_access,
        sections=_sections(view, line),
    )


def _sections(view: ChartView, line: Callable[[str], str]) -> list[SectionBody]:
    built = chart_sections(
        sun_sign=view.sun_sign,
        moon_sign=view.moon_sign,
        ascendant_sign=view.ascendant_sign,
        houses=view.houses,
        planets=tuple((item.name, item.sign) for item in view.planets),
        aspects=view.aspects,
        line=line,
    )
    return [SectionBody(id=item.id, title=item.title, body=item.body) for item in built]


def _planet(item: PlanetPlacement) -> PlanetBody:
    return PlanetBody(
        name=item.name,
        longitude=item.longitude,
        sign=item.sign,
        element=item.element,
        modality=item.modality,
        ruler=item.ruler,
        decan=item.decan,
        decan_ruler=item.decan_ruler,
        retrograde=item.retrograde,
        exact=item.exact,
    )


def _sky(payload: dict[str, object]) -> SkyBody:
    bodies = payload.get("bodies")
    listed: list[PlanetBody] = []
    if isinstance(bodies, list):
        for item in bodies:
            if not isinstance(item, dict):
                continue
            longitude = _float(item.get("longitude"))
            facts = facts_for_longitude(longitude)
            listed.append(
                PlanetBody(
                    name=_text(item, "name"),
                    longitude=longitude,
                    sign=facts.sign,
                    element=facts.element,
                    modality=facts.modality,
                    ruler=facts.ruler,
                    decan=facts.decan,
                    decan_ruler=facts.decan_ruler,
                    retrograde=_bool(item.get("retrograde")),
                    exact=True,
                )
            )
    return SkyBody(
        sun_sign=_text(payload, "sun_sign"),
        moon_sign=_text(payload, "moon_sign"),
        phase_name=_text(payload, "phase_name"),
        bodies=listed,
    )


def _access(feature: str, decision: QuotaDecision) -> AccessBody:
    reset_at = decision.reset_at if isinstance(decision, LimitReached) else None
    if isinstance(decision, Allowed):
        name = "allowed"
    elif isinstance(decision, LimitReached):
        name = "limit_reached"
    else:
        name = "premium_required"
    return AccessBody(feature=feature, decision=name, reset_at=reset_at)


def _text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise Conflict("stored result is incomplete")
    return value


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise Conflict("stored result is incomplete")
    return float(value)


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise Conflict("stored result is incomplete")
    return value
