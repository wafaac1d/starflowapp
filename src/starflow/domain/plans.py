from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

from starflow.domain.features import GATES, PERIODS

Gate = Literal["open", "metered", "capacity", "premium"]
Window = Literal["user_week", "paid_period"]


@dataclass(frozen=True)
class FeatureRule:
    code: str
    gate: Gate
    limit: int | None
    window: Window | None
    requires_entitlement: bool


@dataclass(frozen=True)
class PremiumPlan:
    code: str
    price_stars: int
    period_days: int
    assistant_questions: int
    grace_hours: int
    reminder_days: int


@dataclass(frozen=True)
class TrialPlan:
    days: int
    once: bool


@dataclass(frozen=True)
class GiftPlan:
    days: int


@dataclass(frozen=True)
class ReferralPlan:
    reward_days: int


@dataclass(frozen=True)
class FreePlan:
    compatibility_per_week: int
    favorites_limit: int
    related_profiles_limit: int


@dataclass(frozen=True)
class Plans:
    premium: PremiumPlan
    trial: TrialPlan
    gift: GiftPlan
    referral: ReferralPlan
    free: FreePlan
    features: dict[str, FeatureRule]

    def rule(self, code: str) -> FeatureRule:
        try:
            return self.features[code]
        except KeyError as error:
            raise KeyError(code) from error


def load_plans(path: Path) -> Plans:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("plans.yaml must be a mapping")
    premium = _mapping(loaded, "premium")
    trial = _mapping(loaded, "trial")
    gift = _mapping(loaded, "gift")
    referral = _mapping(loaded, "referral")
    free = _mapping(loaded, "free")
    features = _features(_mapping(loaded, "features"))
    price_stars = _positive(premium, "price_stars")
    period_days = _positive(premium, "period_days")
    if price_stars > 10000:
        raise ValueError("plans.yaml price_stars must be from 1 to 10000")
    if period_days != 30:
        raise ValueError("plans.yaml period_days must be 30")
    once = trial.get("once")
    if once is not True:
        raise ValueError("plans.yaml trial.once must be true")
    parsed = Plans(
        premium=PremiumPlan(
            code=_text(premium, "code"),
            price_stars=price_stars,
            period_days=period_days,
            assistant_questions=_positive(premium, "assistant_questions"),
            grace_hours=_positive(premium, "grace_hours"),
            reminder_days=_positive(premium, "reminder_days"),
        ),
        trial=TrialPlan(days=_positive(trial, "days"), once=True),
        gift=GiftPlan(days=_positive(gift, "days")),
        referral=ReferralPlan(reward_days=_positive(referral, "reward_days")),
        free=FreePlan(
            compatibility_per_week=_positive(free, "compatibility_per_week"),
            favorites_limit=_positive(free, "favorites_limit"),
            related_profiles_limit=_positive(free, "related_profiles_limit"),
        ),
        features=features,
    )
    _agree(parsed, "compatibility", parsed.free.compatibility_per_week)
    _agree(parsed, "favorite", parsed.free.favorites_limit)
    _agree(parsed, "related_profile", parsed.free.related_profiles_limit)
    _agree(parsed, "assistant", parsed.premium.assistant_questions)
    return parsed


def _features(source: dict[str, object]) -> dict[str, FeatureRule]:
    parsed: dict[str, FeatureRule] = {}
    for code, raw in source.items():
        if not isinstance(raw, dict):
            raise ValueError(f"plans.yaml features.{code} must be a mapping")
        gate = raw.get("gate")
        if gate not in GATES:
            raise ValueError(f"plans.yaml features.{code} gate is unknown")
        parsed_gate = cast(Gate, gate)
        window = raw.get("window")
        if window not in PERIODS and window is not None:
            raise ValueError(f"plans.yaml features.{code} window is unknown")
        parsed_window = cast(Window | None, window)
        limit = raw.get("limit")
        if limit is None:
            parsed_limit = None
        elif isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError(f"plans.yaml features.{code} limit must be positive")
        else:
            parsed_limit = limit
        requires = raw.get("requires_entitlement", parsed_gate == "premium")
        if not isinstance(requires, bool):
            raise ValueError(f"plans.yaml features.{code} requires_entitlement must be bool")
        if parsed_gate == "metered" and (parsed_limit is None or parsed_window is None):
            raise ValueError(f"plans.yaml features.{code} needs limit and window")
        if parsed_gate == "capacity" and parsed_limit is None:
            raise ValueError(f"plans.yaml features.{code} needs limit")
        open_has_limit = parsed_limit is not None or parsed_window is not None or requires
        if parsed_gate == "open" and open_has_limit:
            raise ValueError(f"plans.yaml features.{code} must stay open")
        parsed[code] = FeatureRule(code, parsed_gate, parsed_limit, parsed_window, requires)
    return parsed


def _agree(plans: Plans, code: str, expected: int) -> None:
    rule = plans.rule(code)
    if rule.limit != expected:
        raise ValueError(f"plans.yaml features.{code} limit must match the plan number")


def _mapping(source: dict[str, object], key: str) -> dict[str, object]:
    value = source.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"plans.yaml missing {key}")
    return {str(item_key): item for item_key, item in value.items()}


def _text(source: dict[str, object], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"plans.yaml {key} must be text")
    return value


def _positive(source: dict[str, object], key: str) -> int:
    value = source.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"plans.yaml {key} must be a positive integer")
    return value
