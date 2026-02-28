"""SQLite schema and helpers for MTR runs."""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "mtr.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                src TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                hop_count INTEGER NOT NULL,
                host TEXT NOT NULL,
                loss_pct REAL NOT NULL,
                snt INTEGER,
                last_ms REAL,
                avg_ms REAL,
                best_ms REAL,
                wrst_ms REAL,
                stdev REAL,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_target ON runs(target)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hubs_run ON hubs(run_id)")
        conn.commit()
    finally:
        conn.close()


def save_run(target: str, src: Optional[str], hubs: list[dict]) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO runs (target, src) VALUES (?, ?)",
            (target, src or "")
        )
        run_id = cur.lastrowid
        for h in hubs:
            conn.execute(
                """INSERT INTO hubs (run_id, hop_count, host, loss_pct, snt, last_ms, avg_ms, best_ms, wrst_ms, stdev)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    h.get("count", 0),
                    h.get("host", "???"),
                    h.get("Loss%", 0.0),
                    h.get("Snt", 0),
                    h.get("Last", 0.0),
                    h.get("Avg", 0.0),
                    h.get("Best", 0.0),
                    h.get("Wrst", 0.0),
                    h.get("StDev", 0.0),
                ),
            )
        conn.commit()
        return run_id
    finally:
        conn.close()


def get_latest_run(target: Optional[str] = None):
    """Get latest run with hubs. If target is None, latest overall."""
    conn = get_connection()
    try:
        if target:
            row = conn.execute(
                "SELECT id, target, src, created_at FROM runs WHERE target = ? ORDER BY created_at DESC LIMIT 1",
                (target,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, target, src, created_at FROM runs ORDER BY created_at DESC LIMIT 1",
            ).fetchone()
        if not row:
            return None
        run_id, run_target, src, created_at = row
        hubs = conn.execute(
            """SELECT hop_count, host, loss_pct, snt, last_ms, avg_ms, best_ms, wrst_ms, stdev
               FROM hubs WHERE run_id = ? ORDER BY hop_count""",
            (run_id,),
        ).fetchall()
        return {
            "id": run_id,
            "target": run_target,
            "src": src,
            "created_at": created_at,
            "hubs": [
                {
                    "count": h[0],
                    "host": h[1],
                    "Loss%": h[2],
                    "Snt": h[3],
                    "Last": h[4],
                    "Avg": h[5],
                    "Best": h[6],
                    "Wrst": h[7],
                    "StDev": h[8],
                }
                for h in hubs
            ],
        }
    finally:
        conn.close()


def get_runs(target: Optional[str] = None, limit: int = 50):
    """List recent runs for dropdown/history. Includes reached_destination (False if last hop was ??? or 100% loss)."""
    conn = get_connection()
    try:
        if target:
            rows = conn.execute(
                """SELECT r.id, r.target, r.created_at,
                    COALESCE((SELECT CASE WHEN h.host = '???' OR h.loss_pct >= 100 THEN 0 ELSE 1 END
                      FROM hubs h WHERE h.run_id = r.id ORDER BY h.hop_count DESC LIMIT 1), 0) AS reached
                   FROM runs r WHERE r.target = ? ORDER BY r.created_at DESC LIMIT ?""",
                (target, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT r.id, r.target, r.created_at,
                    COALESCE((SELECT CASE WHEN h.host = '???' OR h.loss_pct >= 100 THEN 0 ELSE 1 END
                      FROM hubs h WHERE h.run_id = r.id ORDER BY h.hop_count DESC LIMIT 1), 0) AS reached
                   FROM runs r ORDER BY r.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {"id": r[0], "target": r[1], "created_at": r[2], "reached_destination": bool(r[3])}
            for r in rows
        ]
    finally:
        conn.close()


def get_aggregate(
    from_ts: str,
    to_ts: str,
    target: Optional[str] = None,
):
    """Aggregate hub stats for runs in [from_ts, to_ts]. from_ts/to_ts as ISO or 'YYYY-MM-DD HH:MM:SS'."""
    conn = get_connection()
    try:
        if target:
            run_rows = conn.execute(
                "SELECT id FROM runs WHERE created_at >= ? AND created_at <= ? AND target = ? ORDER BY created_at",
                (from_ts, to_ts, target),
            ).fetchall()
        else:
            run_rows = conn.execute(
                "SELECT id FROM runs WHERE created_at >= ? AND created_at <= ? ORDER BY created_at",
                (from_ts, to_ts),
            ).fetchall()
        run_ids = [r[0] for r in run_rows]
        if not run_ids:
            return {"from": from_ts, "to": to_ts, "target": target, "runs_count": 0, "hubs": []}
        placeholders = ",".join("?" * len(run_ids))
        rows = conn.execute(
            f"""SELECT hop_count, host, loss_pct, best_ms, avg_ms, wrst_ms
                FROM hubs WHERE run_id IN ({placeholders})
                ORDER BY hop_count""",
            run_ids,
        ).fetchall()
        # Group by hop_count
        by_hop: dict[int, list] = {}
        for r in rows:
            hc = r[0]
            if hc not in by_hop:
                by_hop[hc] = []
            by_hop[hc].append({"host": r[1], "loss_pct": r[2], "best_ms": r[3], "avg_ms": r[4], "wrst_ms": r[5]})
        hubs = []
        for hop_count in sorted(by_hop.keys()):
            items = by_hop[hop_count]
            hosts = [x["host"] for x in items if x["host"] and x["host"].strip() != "???"]
            best_vals = [x["best_ms"] for x in items if x["best_ms"] is not None]
            wrst_vals = [x["wrst_ms"] for x in items if x["wrst_ms"] is not None]
            avg_vals = [x["avg_ms"] for x in items if x["avg_ms"] is not None]
            loss_vals = [x["loss_pct"] for x in items if x["loss_pct"] is not None]
            hubs.append({
                "count": hop_count,
                "host": max(set(hosts), key=hosts.count) if hosts else "???",
                "Loss%": sum(loss_vals) / len(loss_vals) if loss_vals else 0,
                "Best": min(best_vals) if best_vals else None,
                "Wrst": max(wrst_vals) if wrst_vals else None,
                "Avg": sum(avg_vals) / len(avg_vals) if avg_vals else None,
                "runs_count": len(items),
            })
        return {
            "from": from_ts,
            "to": to_ts,
            "target": target,
            "runs_count": len(run_ids),
            "hubs": hubs,
        }
    finally:
        conn.close()


def get_runs_in_range(
    from_ts: str,
    to_ts: str,
    target: Optional[str] = None,
) -> list[dict]:
    """Returns runs in [from_ts, to_ts] with full hubs (for timeline)."""
    conn = get_connection()
    try:
        if target:
            run_rows = conn.execute(
                "SELECT id, target, created_at FROM runs WHERE created_at >= ? AND created_at <= ? AND target = ? ORDER BY created_at",
                (from_ts, to_ts, target),
            ).fetchall()
        else:
            run_rows = conn.execute(
                "SELECT id, target, created_at FROM runs WHERE created_at >= ? AND created_at <= ? ORDER BY created_at",
                (from_ts, to_ts),
            ).fetchall()
        result = []
        for rid, run_target, created_at in run_rows:
            hubs = conn.execute(
                """SELECT hop_count, host, loss_pct, snt, last_ms, avg_ms, best_ms, wrst_ms, stdev
                   FROM hubs WHERE run_id = ? ORDER BY hop_count""",
                (rid,),
            ).fetchall()
            result.append({
                "id": rid,
                "target": run_target,
                "created_at": created_at,
                "hubs": [
                    {
                        "count": h[0],
                        "host": h[1],
                        "Loss%": h[2],
                        "Snt": h[3],
                        "Last": h[4],
                        "Avg": h[5],
                        "Best": h[6],
                        "Wrst": h[7],
                        "StDev": h[8],
                    }
                    for h in hubs
                ],
            })
        return result
    finally:
        conn.close()


def get_run(run_id: int):
    """Get single run with hubs by id."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, target, src, created_at FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        rid, run_target, src, created_at = row
        hubs = conn.execute(
            """SELECT hop_count, host, loss_pct, snt, last_ms, avg_ms, best_ms, wrst_ms, stdev
               FROM hubs WHERE run_id = ? ORDER BY hop_count""",
            (rid,),
        ).fetchall()
        return {
            "id": rid,
            "target": run_target,
            "src": src,
            "created_at": created_at,
            "hubs": [
                {
                    "count": h[0],
                    "host": h[1],
                    "Loss%": h[2],
                    "Snt": h[3],
                    "Last": h[4],
                    "Avg": h[5],
                    "Best": h[6],
                    "Wrst": h[7],
                    "StDev": h[8],
                }
                for h in hubs
            ],
        }
    finally:
        conn.close()
