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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from app import app  # noqa: E402

DOCS = ROOT / "docs"


def fix(html, page):
    """Rewrite Flask absolute URLs to paths that work under GitHub Pages."""
    html = html.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    html = html.replace('href="/how-to-read-radar"', 'href="how-to-read-radar.html"')
    html = html.replace('href="/"', 'href="index.html"')
    if page == "index":
        html = html.replace('<script src="static/app.js">', '<script>window.STATS_URL = "stats.json";</script>\n<script src="static/app.js">')
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

    client = app.test_client()
    pages = {"index": "/", "how-to-read-radar": "/how-to-read-radar"}
    for name, url in pages.items():
        html = client.get(url).get_data(as_text=True)
        (DOCS / f"{name}.html").write_text(fix(html, name), encoding="utf-8")

    for sub in ("static", "outputs"):
        if (DOCS / sub).exists():
            shutil.rmtree(DOCS / sub)
    shutil.copytree(ROOT / "app" / "static", DOCS / "static")
    (DOCS / "outputs").mkdir()
    for layer in stats["layers"].values():
        name = Path(layer["url"]).name
        shutil.copy(ROOT / "outputs" / name, DOCS / "outputs" / name)
        layer["url"] = "outputs/" + name              # relative: works under /<repo-name>/
    (DOCS / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    print("static site written to", DOCS)


if __name__ == "__main__":
    main()
