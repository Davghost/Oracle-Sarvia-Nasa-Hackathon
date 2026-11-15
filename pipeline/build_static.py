"""Build a static copy of the web app into docs/ so GitHub Pages can serve it (no Flask needed).

Run:  python pipeline/build_static.py
Then in GitHub: Settings > Pages > Deploy from a branch > main > /docs.
Re-run after every change to app/ or outputs/stats.json, then commit docs/.
"""
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from app import app  # noqa: E402

DOCS = ROOT / "docs"


def fix(html, page):
    """Rewrite Flask absolute URLs to paths that work under GitHub Pages."""
    html = html.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    html = html.replace('href="/workspace"', 'href="workspace.html"')
    html = html.replace('href="/how-to-read-radar"', 'href="how-to-read-radar.html"')
    html = html.replace('href="/"', 'href="index.html"')
    if page in {"index", "workspace"}:
        html = html.replace(
            '<script src="static/app.js">',
            f'<script>window.STATS_URL = "stats.json"; window.SARVIA_MAP_CONFIG = {{}}; window.SARVIA_WORKSPACE = {str(page == "workspace").lower()};</script>\n'
            '<script src="static/app.js">',
        )
    return html


def main():
    # Publishing mock results would make the public page look like a real
    # scientific result, so the build stops unless the pipeline produced data.
    stats_src = ROOT / "outputs" / "stats.json"
    if not stats_src.exists():
        raise SystemExit("outputs/stats.json not found: run the pipeline first (this would publish mock data).")
    stats = json.loads(stats_src.read_text(encoding="utf-8"))
    if stats.get("mock"):
        raise SystemExit("stats.json is mock data. Refusing to build the public site.")

    # Validate and resolve all local assets before replacing the previous
    # published copy, so a missing layer cannot leave docs/ half-built.
    local_layers = []
    outputs_root = (ROOT / "outputs").resolve()
    for layer_name, layer in stats.get("layers", {}).items():
        raw_url = layer.get("url")
        if not isinstance(raw_url, str) or not raw_url:
            raise SystemExit(f"layer {layer_name!r} has no valid URL")
        parts = urlsplit(raw_url)
        if parts.scheme or parts.netloc:
            if parts.scheme not in {"http", "https"}:
                raise SystemExit(f"layer {layer_name!r} uses unsupported URL: {raw_url}")
            continue
        source_path = Path(unquote(parts.path))
        if source_path.is_absolute():
            source_path = source_path.relative_to("/")
        if source_path.parts[:1] != ("outputs",):
            raise SystemExit(f"local layer {layer_name!r} must be under /outputs/: {raw_url}")
        source = (ROOT / source_path).resolve()
        if not source.is_relative_to(outputs_root):
            raise SystemExit(f"local layer {layer_name!r} escapes outputs/: {raw_url}")
        if not source.is_file():
            raise SystemExit(f"layer file not found for {layer_name!r}: {source}")
        local_layers.append((layer, parts, source, source.relative_to(outputs_root)))

    client = app.test_client()
    pages = {"index": "/", "workspace": "/workspace", "how-to-read-radar": "/how-to-read-radar"}
    rendered_pages = {}
    for name, url in pages.items():
        response = client.get(url)
        if response.status_code != 200:
            raise SystemExit(f"could not render {url}: HTTP {response.status_code}")
        rendered_pages[name] = fix(response.get_data(as_text=True), name)

    for sub in ("static", "outputs"):
        if (DOCS / sub).exists():
            shutil.rmtree(DOCS / sub)
    shutil.copytree(ROOT / "app" / "static", DOCS / "static")
    for name, html in rendered_pages.items():
        (DOCS / f"{name}.html").write_text(html, encoding="utf-8")
    (DOCS / "outputs").mkdir()
    for layer, parts, source, relative in local_layers:
        destination = DOCS / "outputs" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        layer["url"] = urlunsplit(("", "", "outputs/" + relative.as_posix(), parts.query, parts.fragment))
    (DOCS / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    print("static site written to", DOCS)


if __name__ == "__main__":
    main()
