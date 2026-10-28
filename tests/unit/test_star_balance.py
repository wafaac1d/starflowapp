from starflow.domain.stars import (
    COMPATIBILITY_STARS,
    NATAL_STARS,
    QUESTION_STARS,
    pair_subject,
    purchase_effect,
    settle_spend,
    topup_amount_ok,
)


def test_prices_and_pair_subject() -> None:
    assert NATAL_STARS == 40
    assert COMPATIBILITY_STARS == 40
    assert QUESTION_STARS == 20
    assert pair_subject("Лев", "телец") == pair_subject("телец", "лев")
    assert pair_subject("лев", "телец") == "лев:телец"
    try:
        pair_subject("лев", "не знак")
    except ValueError:
        rejected = True
    else:
        rejected = False
    assert rejected is True


def test_spend_does_not_charge_twice_or_go_negative() -> None:
    short = settle_spend(19, QUESTION_STARS, already=False)
    assert short.allowed is False
    assert short.charged is False
    assert short.balance == 19
    paid = settle_spend(40, NATAL_STARS, already=False)
    assert paid.allowed is True
    assert paid.charged is True
    assert paid.balance == 0
    again = settle_spend(0, NATAL_STARS, already=True)
    assert again.allowed is True
    assert again.charged is False
    assert again.balance == 0


def test_topup_credits_balance_and_client_status_does_not() -> None:
    assert purchase_effect("topup") == "balance"
    assert purchase_effect("subscription") == "premium"
    assert purchase_effect("gift") == "gift"
    assert topup_amount_ok(10) is True
    assert topup_amount_ok(10000) is True
    assert topup_amount_ok(0) is False
    assert topup_amount_ok(10001) is False
