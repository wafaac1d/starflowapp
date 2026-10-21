from pathlib import Path

from starflow.api.spa import SpaKind, resolve_spa


def test_api_and_missing_asset_are_not_client_routes(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>starflow</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")

    assert resolve_spa(dist, logo, "/api/v1/missing").kind is SpaKind.MISSING_API
    assert resolve_spa(dist, logo, "/assets/missing.js").kind is SpaKind.MISSING_ASSET
    assert resolve_spa(dist, logo, "/assets/app.js").kind is SpaKind.FILE
    assert resolve_spa(dist, logo, "/reading").kind is SpaKind.HTML
    assert resolve_spa(dist, logo, "/logo.png").file == logo
    escaped = resolve_spa(dist, logo, "/../secret.txt")
    assert escaped.kind is SpaKind.MISSING_ASSET
