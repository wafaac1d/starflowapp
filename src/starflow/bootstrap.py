from collections.abc import Callable
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncEngine

from starflow.ai.catalog import load_prompts
from starflow.ai.client import DeepSeekClient
from starflow.ai.prompts import PromptLibrary
from starflow.astro.swiss import SwissEphemeris
from starflow.bot.handlers import UpdateContextMiddleware, register_handlers
from starflow.bot.runtime import BotRuntime
from starflow.bot.session import InactiveTelegramSession
from starflow.bot.stars import AiogramStarGateway
from starflow.cache.memory import MemoryCache
from starflow.cache.postgres import PostgresLevelTwo
from starflow.cache.ttl import TtlCache
from starflow.cache.two_level import TwoLevelCache
from starflow.config import Settings
from starflow.db.engine import create_db_engine, create_session_factory
from starflow.db.lock import SingletonLock
from starflow.domain.plans import Plans
from starflow.i18n.catalog import Catalog, load_catalog, require_keys
from starflow.logging import configure_logging, get_logger
from starflow.repositories.uow import SqlUnitOfWork
from starflow.scheduler.runtime import SchedulerRuntime
from starflow.services.access import AccessService
from starflow.services.billing import BillingService
from starflow.services.chart import ChartService
from starflow.services.forecast import ForecastService
from starflow.services.health import HealthService
from starflow.services.nominatim import NominatimLookup
from starflow.services.outbox import OutboxService
from starflow.services.places import PlaceService, RequestPace
from starflow.services.profile import ProfileService
from starflow.services.quota import QuotaService
from starflow.services.session import SessionService
from starflow.services.sky import SkyService
from starflow.services.telegram_auth import TelegramInitDataVerifier
from starflow.services.timezones import FinderTimezone

REQUIRED_TEXTS = (
    "ui.home.title",
    "ui.home.lead",
    "ui.home.disclaimer",
    "ui.home.logo_label",
    "ui.home.price_label",
    "bot.start",
    "bot.start_without_app",
    "bot.open",
    "bot.start_missing_user",
    "bot.digest",
    "bot.help",
    "bot.profile",
    "bot.settings",
    "bot.premium",
    "bot.terms",
    "bot.paysupport",
    "bot.delete_ask",
    "bot.delete_confirm",
    "bot.delete_done",
    "bot.delete_missing",
    "bot.menu",
    "bot.command_start",
    "bot.command_help",
    "bot.command_profile",
    "bot.command_settings",
    "bot.command_premium",
    "bot.command_terms",
    "bot.command_paysupport",
    "bot.command_delete_me",
    "errors.unauthorized",
    "errors.not_found",
    "errors.validation",
    "errors.webhook_rejected",
    "errors.premium_required",
    "errors.name_required",
    "errors.name_too_long",
    "errors.date_invalid",
    "errors.date_future",
    "errors.time_invalid",
    "errors.timezone_invalid",
    "errors.place_mismatch",
    "errors.place_timezone",
    "errors.onboarding_incomplete",
    "errors.place_required",
    "errors.place_not_offered",
    "errors.limit_reached",
    "errors.idempotency_key",
    "errors.related_required",
    "errors.conflict",
    "errors.reading_failed",
    "errors.payment_check",
    "errors.payment_unavailable",
    "errors.gift_invalid",
    "errors.gift_self",
    "errors.trial_used",
    "errors.payment_confirm",
    "bot.subscription_ending",
    "bot.invoice_subscription_title",
    "bot.invoice_subscription_description",
    "bot.invoice_gift_title",
    "bot.invoice_gift_description",
    "ui.reading.day",
    "ui.reading.week",
    "ui.reading.advice",
    "ui.reading.moon",
    "ui.reading.compatibility",
    "ui.reading.fallback_day",
    "ui.reading.fallback_week",
    "ui.reading.fallback_advice",
    "ui.reading.fallback_moon",
    "ui.reading.fallback_compatibility",
    "ui.chart.title",
    "ui.chart.sun",
    "ui.chart.calendar_source",
    "ui.chart.ephemeris_source",
    "ui.chart.moon_unknown",
    "ui.chart.asc_unknown",
    "ui.chart.houses_unknown",
    "ui.chart.time_unknown",
    "ui.chart.place_missing",
    "ui.chart.local_time_ambiguous",
    "ui.chart.local_time_gap",
    "ui.chart.timezone_missing",
    "ui.chart.birth_date_missing",
    "ui.chart.houses_unavailable",
    "ui.chart.lunar_day",
    "ui.chart.phase",
    "ui.chart.planets",
    "ui.chart.transits",
    "ui.chart.retrograde",
    "ui.paywall.title",
    "ui.paywall.lead",
    "ui.place.attribution",
    "ui.sky.title",
    "ui.sky.lead",
    "ui.open.title",
    "ui.open.lead",
    "ui.common.back",
    "ui.common.next",
    "ui.common.cancel",
    "ui.common.retry",
    "ui.common.loading",
    "ui.common.error",
    "ui.onboarding.welcome_title",
    "ui.onboarding.welcome_lead",
    "ui.onboarding.name_title",
    "ui.onboarding.date_title",
    "ui.onboarding.time_title",
    "ui.onboarding.time_unknown",
    "ui.onboarding.timezone_title",
    "ui.onboarding.place_title",
    "ui.onboarding.sign_title",
    "ui.profile.title",
    "ui.profile.save",
    "ui.profile.delete",
    "ui.profile.delete_confirm",
    "ui.settings.title",
    "ui.premium.title",
    "ui.terms.title",
    "ui.help.title",
    "ui.paysupport.title",
)


@dataclass
class Container:
    settings: Settings
    plans: Plans
    catalog: Catalog
    engine: AsyncEngine
    deepseek: DeepSeekClient
    session_service: SessionService
    profile_service: ProfileService
    place_service: PlaceService
    access_service: AccessService
    quota_service: QuotaService
    chart_service: ChartService
    forecast_service: ForecastService
    billing_service: BillingService
    sky_service: SkyService
    uow_factory: Callable[[], SqlUnitOfWork]
    health_service: HealthService
    outbox_service: OutboxService
    verifier: TelegramInitDataVerifier
    bot: Bot
    dispatcher: Dispatcher
    bot_runtime: BotRuntime
    scheduler_runtime: SchedulerRuntime
    lock: SingletonLock | None

    async def startup(self) -> None:
        if self.lock is not None:
            await self.lock.acquire()
        self.scheduler_runtime.start()
        await self.bot_runtime.start()

    async def shutdown(self) -> None:
        await self.bot_runtime.shutdown()
        await self.scheduler_runtime.shutdown()
        if self.lock is not None:
            await self.lock.release()
        await self.deepseek.aclose()
        await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    configure_logging(settings.log_level)
    log = get_logger("bootstrap")
    plans = settings.runtime_plans()
    log.info("plans_loaded", plan_code=plans.premium.code, price_stars=plans.premium.price_stars)
    cache = MemoryCache(settings.memory_cache_size)
    catalog = load_catalog(settings.resources_dir, settings.default_locale, cache)
    require_keys(catalog, REQUIRED_TEXTS)
    PromptLibrary(settings.resources_dir / "prompts").assistant_system()
    prompts = load_prompts(settings.resources_dir / "prompts" / "forecasts.yaml")
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    def uow_factory() -> SqlUnitOfWork:
        return SqlUnitOfWork(session_factory)

    session_service = SessionService(
        uow_factory, frozenset(settings.admin_ids), settings.session_ttl_sec
    )
    profile_service = ProfileService(
        uow_factory, FinderTimezone(), default_timezone=settings.default_timezone
    )
    place_service = PlaceService(
        uow_factory,
        NominatimLookup(settings.nominatim_base_url, settings.nominatim_user_agent),
        RequestPace(),
    )
    access_service = AccessService(uow_factory)
    ephemeris = SwissEphemeris()
    quota_service = QuotaService(uow_factory, plans)
    sky_service = SkyService(uow_factory, ephemeris)
    chart_service = ChartService(uow_factory, ephemeris, quota_service, sky_service)
    deepseek = DeepSeekClient(settings)
    forecast_cache = TwoLevelCache(
        TtlCache(settings.memory_cache_size), PostgresLevelTwo(uow_factory)
    )
    forecast_service = ForecastService(
        uow_factory,
        forecast_cache,
        deepseek,
        prompts,
        catalog,
        quota_service,
        sky_service,
        fast_model=settings.deepseek_model_fast,
        pro_model=settings.deepseek_model_pro,
        zone_name=settings.default_timezone,
        locale=settings.default_locale,
        mini_app_url=settings.mini_app_url,
    )
    outbox_service = OutboxService(uow_factory, catalog)
    health_service = HealthService(engine)
    verifier = TelegramInitDataVerifier(
        settings.bot_token, settings.auth_max_age_sec, settings.auth_future_skew_sec
    )
    session = InactiveTelegramSession() if settings.app_env == "test" else AiohttpSession()
    bot = Bot(token=settings.bot_token, session=session, default=DefaultBotProperties())
    billing_service = BillingService(
        uow_factory,
        AiogramStarGateway(bot),
        plans,
        settings.payment_hmac_secret,
        catalog,
        settings.mini_app_url,
    )
    dispatcher = Dispatcher()
    dispatcher.update.middleware(UpdateContextMiddleware())
    router = Router()
    register_handlers(router, session_service, catalog, settings.mini_app_url, billing_service)
    dispatcher.include_router(router)
    commands = tuple(
        BotCommand(command=name, description=catalog.text(key))
        for name, key in (
            ("start", "bot.command_start"),
            ("help", "bot.command_help"),
            ("profile", "bot.command_profile"),
            ("settings", "bot.command_settings"),
            ("premium", "bot.command_premium"),
            ("terms", "bot.command_terms"),
            ("paysupport", "bot.command_paysupport"),
            ("delete_me", "bot.command_delete_me"),
        )
    )
    bot_runtime = BotRuntime(settings, bot, dispatcher, commands, catalog.text("bot.menu"))
    scheduler_runtime = SchedulerRuntime(settings, outbox_service, bot_runtime, billing_service)
    return Container(
        settings=settings,
        plans=plans,
        catalog=catalog,
        engine=engine,
        deepseek=deepseek,
        session_service=session_service,
        profile_service=profile_service,
        place_service=place_service,
        access_service=access_service,
        quota_service=quota_service,
        chart_service=chart_service,
        forecast_service=forecast_service,
        billing_service=billing_service,
        sky_service=sky_service,
        uow_factory=uow_factory,
        health_service=health_service,
        outbox_service=outbox_service,
        verifier=verifier,
        bot=bot,
        dispatcher=dispatcher,
        bot_runtime=bot_runtime,
        scheduler_runtime=scheduler_runtime,
        lock=SingletonLock(engine) if settings.singleton_lock else None,
    )
