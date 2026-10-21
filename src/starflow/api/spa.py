from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SpaKind(StrEnum):
    FILE = "file"
    HTML = "html"
    MISSING_ASSET = "missing_asset"
    MISSING_API = "missing_api"
    MISSING_CLIENT = "missing_client"


@dataclass(frozen=True)
class SpaDecision:
    kind: SpaKind
    file: Path | None = None


def resolve_spa(dist: Path, logo: Path, url_path: str) -> SpaDecision:
    relative = url_path.split("?", 1)[0]
    if relative != "/" and relative.endswith("/"):
        relative = relative[:-1]
    if relative == "/api" or relative.startswith("/api/"):
        return SpaDecision(SpaKind.MISSING_API)
    if _is_asset(relative):
        found = _safe_file(dist, relative)
        if relative == "/logo.png" and (found is None or not found.is_file()) and logo.is_file():
            return SpaDecision(SpaKind.FILE, logo)
        if found is None or not found.is_file():
            return SpaDecision(SpaKind.MISSING_ASSET)
        return SpaDecision(SpaKind.FILE, found)
    index = (dist / "index.html").resolve()
    dist_root = dist.resolve()
    if not index.is_file() or not index.is_relative_to(dist_root):
        return SpaDecision(SpaKind.MISSING_CLIENT)
    return SpaDecision(SpaKind.HTML, index)


def _is_asset(url_path: str) -> bool:
    name = url_path.rsplit("/", 1)[-1]
    return "." in name or url_path.startswith("/assets/")


def _safe_file(dist: Path, url_path: str) -> Path | None:
    candidate = (dist / url_path.lstrip("/")).resolve()
    if not candidate.is_relative_to(dist.resolve()):
        return None
    return candidate
