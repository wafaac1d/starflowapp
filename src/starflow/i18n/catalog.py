from pathlib import Path

import yaml

from starflow.cache.memory import MemoryCache
from starflow.i18n.guard import assert_authored


class Catalog:
    def __init__(self, locale: str, texts: dict[str, str]) -> None:
        self.locale = locale
        self._texts = texts

    def text(self, key: str) -> str:
        try:
            return self._texts[key]
        except KeyError as error:
            raise KeyError(key) from error

    def format(self, key: str, **values: str | int) -> str:
        rendered = self.text(key)
        for name, value in values.items():
            rendered = rendered.replace("{" + name + "}", str(value))
        return rendered

    def plural(self, key: str, count: int) -> str:
        form = "one" if count % 10 == 1 and count % 100 != 11 else "many"
        if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
            form = "few"
        return self.format(f"{key}.{form}", count=count)


def load_catalog(directory: Path, locale: str, cache: MemoryCache) -> Catalog:
    cache_key = f"catalog:{locale}:{directory}"
    cached = cache.get(cache_key)
    if isinstance(cached, Catalog):
        return cached
    locale_dir = directory / "texts" / locale
    texts: dict[str, str] = {}
    for path in sorted(locale_dir.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path.name} must be a mapping")
        texts.update(_flatten(path.stem, loaded))
    for key, value in texts.items():
        assert_authored(value)
        if not value.strip():
            raise ValueError(f"empty text for {key}")
    catalog = Catalog(locale, texts)
    cache.set(cache_key, catalog)
    return catalog


def require_keys(catalog: Catalog, keys: tuple[str, ...]) -> None:
    for key in keys:
        catalog.text(key)


def _flatten(prefix: str, value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{prefix} must be a mapping")
    flat: dict[str, str] = {}
    for key, item in value.items():
        child = f"{prefix}.{key}"
        if isinstance(item, str):
            flat[child] = item
        else:
            flat.update(_flatten(child, item))
    return flat
