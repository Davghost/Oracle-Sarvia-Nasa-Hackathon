"""Flask app: serves pre-computed results only. No heavy processing here."""
import json
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, send_from_directory

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

app = Flask(__name__)


def stats_path() -> Path:
    """Real results win; fall back to mock data while the pipeline is not ready."""
    real = OUTPUTS / "stats.json"
    return real if real.exists() else OUTPUTS / "mock" / "stats.json"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/stats")
def api_stats():
    path = stats_path()
    if not path.exists():
        abort(404, "stats.json not found")
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.get("/outputs/<path:name>")
def outputs(name):
    return send_from_directory(OUTPUTS, name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
