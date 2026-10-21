from timezonefinder import TimezoneFinder


class FinderTimezone:
    """Пояс по координатам без сети."""

    def __init__(self) -> None:
        self._finder = TimezoneFinder()

    def zone(self, latitude: float, longitude: float) -> str | None:
        found = self._finder.timezone_at(lat=latitude, lng=longitude)
        if isinstance(found, str) and found:
            return found
        return None
