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
            found = geocoder.geocode(
                query,
                exactly_one=False,
                limit=5,
                language="ru",
                addressdetails=True,
            )
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
            raw = getattr(item, "raw", None)
            short_label = format_short_place(label.strip(), raw if isinstance(raw, dict) else None)
            hits.append(
                PlaceHit(
                    short_label,
                    Decimal(f"{latitude:.6f}"),
                    Decimal(f"{longitude:.6f}"),
                )
            )
        return hits


def format_short_place(address_text: str, raw: dict[str, object] | None = None) -> str:
    if raw and isinstance(raw, dict):
        addr = raw.get("address")
        if isinstance(addr, dict):
            country = addr.get("country")
            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("municipality")
                or addr.get("state")
                or raw.get("name")
            )
            if country and city and isinstance(country, str) and isinstance(city, str):
                country_clean = country.strip()
                city_clean = city.strip()
                if country_clean.lower() == city_clean.lower():
                    return city_clean
                return f"{country_clean}, {city_clean}"

    parts = [p.strip() for p in address_text.split(",") if p.strip()]
    if not parts:
        return address_text.strip()
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]}, {parts[1]}"

    city = parts[0]
    country = parts[-1]
    if country.isdigit() and len(parts) >= 3:
        country = parts[-2]
    elif country.isdigit():
        return city

    if country.lower() == city.lower():
        return city
    return f"{country}, {city}"
