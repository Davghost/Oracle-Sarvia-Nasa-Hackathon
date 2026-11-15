import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def test_static_site_serves_pages_stats_and_prebuilt_layers():
    handler = partial(QuietHandler, directory=str(DOCS))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(f"{base_url}/") as response:
            page = response.read().decode("utf-8")
            assert response.status == 200
            assert 'window.STATS_URL = "stats.json"' in page
            assert "static/app.js" in page

        with urlopen(f"{base_url}/stats.json") as response:
            stats = json.load(response)
            assert response.status == 200
            assert stats["mock"] is False

        for layer in stats["layers"].values():
            assert layer["type"] == "image"
            with urlopen(f"{base_url}/{layer['url']}") as response:
                assert response.status == 200
                assert response.headers["Content-Type"] == "image/png"

        with urlopen(f"{base_url}/how-to-read-radar.html") as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
