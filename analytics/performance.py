"""
analytics/performance.py — Win-rate analytics from the SQLite trades table.
Queries by session, score range, and regime to surface actionable insights.
"""
from database.db import _raw_conn
from utils.logger import get_logger

logger = get_logger(__name__)


def _fetch(sql: str, params: tuple = ()) -> list:
    conn = _raw_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def get_summary(user_id: int | None = None) -> dict:
    sql = """
        SELECT COUNT(*) t,
               SUM(pnl>0) w,
               ROUND(AVG(pnl),2) avg,
               ROUND(MAX(pnl),2) best,
               ROUND(MIN(pnl),2) worst,
               ROUND(SUM(CASE WHEN pnl>0 THEN pnl ELSE 0 END),2) gw,
               ROUND(SUM(CASE WHEN pnl<=0 THEN ABS(pnl) ELSE 0 END),2) gl
        FROM trades WHERE exit_time IS NOT NULL
    """
    params = ()
    if user_id is not None:
        sql += " AND user_id = ?"
        params = (user_id,)
        
    rows = _fetch(sql, params)
    if not rows or not rows[0]["t"]:
        return {}
    r = rows[0]
    t, w = r["t"], r["w"] or 0
    gl   = r["gl"] or 0
    return {
        "total": t, "wins": w, "losses": t - w,
        "win_rate": round(w / t * 100, 1),
        "avg_pnl":  r["avg"],
        "best": r["best"], "worst": r["worst"],
        "profit_factor": round(r["gw"] / gl, 2) if gl else float("inf"),
    }


def get_by_session(user_id: int | None = None) -> dict:
    sql = """
        SELECT COALESCE(session,'UNKNOWN') s, COUNT(*) t,
               SUM(pnl>0) w
        FROM trades WHERE exit_time IS NOT NULL
    """
    params = ()
    if user_id is not None:
        sql += " AND user_id = ?"
        params = (user_id,)
    sql += " GROUP BY s"
    
    rows = _fetch(sql, params)
    return {
        r["s"]: {"total": r["t"], "wins": r["w"] or 0,
                 "win_rate": round((r["w"] or 0) / r["t"] * 100, 1)}
        for r in rows
    }


def get_by_score(user_id: int | None = None) -> dict:
    sql = """
        SELECT CASE WHEN score>=90 THEN '90-100'
                    WHEN score>=80 THEN '80-89'
                    WHEN score>=70 THEN '70-79'
                    ELSE '<70' END sr,
               COUNT(*) t, SUM(pnl>0) w
        FROM trades WHERE exit_time IS NOT NULL AND score IS NOT NULL
    """
    params = ()
    if user_id is not None:
        sql += " AND user_id = ?"
        params = (user_id,)
    sql += " GROUP BY sr ORDER BY sr DESC"
    
    rows = _fetch(sql, params)
    return {
        r["sr"]: {"total": r["t"], "wins": r["w"] or 0,
                  "win_rate": round((r["w"] or 0) / r["t"] * 100, 1)}
        for r in rows
    }


def get_by_regime(user_id: int | None = None) -> dict:
    sql = """
        SELECT COALESCE(regime,'UNKNOWN') rg, COUNT(*) t, SUM(pnl>0) w
        FROM trades WHERE exit_time IS NOT NULL
    """
    params = ()
    if user_id is not None:
        sql += " AND user_id = ?"
        params = (user_id,)
    sql += " GROUP BY rg"
    
    rows = _fetch(sql, params)
    return {
        r["rg"]: {"total": r["t"], "wins": r["w"] or 0,
                  "win_rate": round((r["w"] or 0) / r["t"] * 100, 1)}
        for r in rows
    }


def print_report() -> None:
    print("\n" + "=" * 55)
    print("📊  PERFORMANCE ANALYTICS")
    print("=" * 55)
    s = get_summary()
    if not s:
        print("  No completed trades yet."); return

    print(f"  Trades: {s['total']}  WinRate: {s['win_rate']}%  PF: {s['profit_factor']}")
    print(f"  AvgPnL: ${s['avg_pnl']}  Best: ${s['best']}  Worst: ${s['worst']}")

    for title, data in [("Session", get_by_session()),
                        ("Score",   get_by_score()),
                        ("Regime",  get_by_regime())]:
        print(f"\n  ── By {title} " + "─" * (40 - len(title)))
        for k, v in data.items():
            print(f"  {k:<18} {v['win_rate']:>5.1f}%  ({v['wins']}/{v['total']})")
    print("=" * 55)
