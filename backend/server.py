"""Flask API and static file server for visual traceroute."""
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from db import init_db, get_latest_run, get_run, get_runs, get_aggregate, get_runs_in_range

app = Flask(__name__, static_folder=None)
CORS(app)

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "frontend"


@app.route("/api/latest")
def api_latest():
    target = request.args.get("target")
    run = get_latest_run(target=target or None)
    if run is None:
        return jsonify({"error": "No runs yet"}), 404
    return jsonify(run)


@app.route("/api/runs")
def api_runs():
    target = request.args.get("target")
    limit = request.args.get("limit", 50, type=int)
    runs = get_runs(target=target or None, limit=limit)
    return jsonify(runs)


@app.route("/api/runs/<int:run_id>")
def api_run(run_id):
    run = get_run(run_id)
    if run is None:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run)


@app.route("/api/aggregate")
def api_aggregate():
    from_ts = request.args.get("from")
    to_ts = request.args.get("to")
    target = request.args.get("target") or None
    if not from_ts or not to_ts:
        return jsonify({"error": "Query params 'from' and 'to' required (ISO datetime)"}), 400
    data = get_aggregate(from_ts=from_ts, to_ts=to_ts, target=target)
    return jsonify(data)


@app.route("/api/runs_range")
def api_runs_range():
    from_ts = request.args.get("from")
    to_ts = request.args.get("to")
    target = request.args.get("target") or None
    if not from_ts or not to_ts:
        return jsonify({"error": "Query params 'from' and 'to' required (ISO datetime)"}), 400
    runs = get_runs_in_range(from_ts=from_ts, to_ts=to_ts, target=target)
    return jsonify({"from": from_ts, "to": to_ts, "runs": runs})


@app.route("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(STATIC, path)


def main():
    init_db()
    port = int(os.environ.get("PORT", "4000"))
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
