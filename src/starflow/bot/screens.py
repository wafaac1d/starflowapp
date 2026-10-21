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
    return f"{base}/{screen}"
