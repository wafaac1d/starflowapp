SCREENS: tuple[str, ...] = (
    "help",
    "profile",
    "settings",
    "premium",
    "terms",
    "paysupport",
)


def screen_url(mini_app_url: str, screen: str) -> str:
    base = mini_app_url.rstrip("/")
    if screen == "home":
        return base
    return f"{base}/{screen}"
