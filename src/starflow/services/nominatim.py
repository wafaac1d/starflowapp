import asyncio
from decimal import Decimal
from urllib.parse import urlsplit

from geopy.exc import GeopyError
from geopy.geocoders import Nominatim

from starflow.domain.records import PlaceHit


class NominatimLookup:
    """Поиск Nominatim через geopy. Вызов идёт после паузы и только по явному действию."""

    def __init__(self, base_url: str, user_agent: str) -> None:
        parts = urlsplit(base_url)
        self._scheme = parts.scheme or "https"
        self._domain = parts.netloc or "nominatim.openstreetmap.org"
        self._user_agent = user_agent

    async def search(self, query: str) -> list[PlaceHit]:
        return await asyncio.to_thread(self._search, query)

    def _search(self, query: str) -> list[PlaceHit]:
        geocoder = Nominatim(
            user_agent=self._user_agent,
            scheme=self._scheme,
            domain=self._domain,
            timeout=10,
        )
        try:
            found = geocoder.geocode(query, exactly_one=False, limit=5, language="ru")
        except GeopyError:
            return []
        if found is None:
            return []
        locations = found if isinstance(found, list) else [found]
        hits: list[PlaceHit] = []
        for item in locations:
            latitude = getattr(item, "latitude", None)
            longitude = getattr(item, "longitude", None)
            label = getattr(item, "address", None)
            if not isinstance(latitude, float) or not isinstance(longitude, float):
                continue
            if not isinstance(label, str) or not label.strip():
                continue
            hits.append(
                PlaceHit(
                    label.strip(),
                    Decimal(f"{latitude:.6f}"),
                    Decimal(f"{longitude:.6f}"),
                )
            )
        return hits
