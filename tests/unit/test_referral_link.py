from starflow.domain.invite import referral_link, referral_redirect_url


def test_referral_link_opens_the_bot_instead_of_the_site() -> None:
    link = referral_link("https://starflow.example", "abc123", "StarFlowBot")
    assert link == "https://t.me/StarFlowBot?start=ref_abc123"


def test_referral_link_keeps_a_telegram_base_when_the_name_is_unknown() -> None:
    link = referral_link("https://t.me/starflow_bot/app", "abc123", "")
    assert link == "https://t.me/starflow_bot/app?startapp=ref_abc123"


def test_referral_link_does_not_hand_out_the_website() -> None:
    assert referral_link("https://starflow.example", "abc123", "") == ""


def test_an_old_site_link_redirects_into_telegram() -> None:
    target = referral_redirect_url("startapp=ref_abc123", "@StarFlowBot")
    assert target == "https://t.me/StarFlowBot?start=ref_abc123"


def test_a_page_without_a_referral_code_stays_on_the_site() -> None:
    assert referral_redirect_url("startapp=gift_1", "StarFlowBot") is None
    assert referral_redirect_url("", "StarFlowBot") is None
