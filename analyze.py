"""
MMA Life Simulator — Game Data Analysis Tool
Analyzes the SQLite database for balance insights, anomalies, and trends.
Usage: python3 analyze.py [report_type]
  reports: all, balance, fighters, promotions, careers
"""

import json
import os
import sqlite3
import sys

DB_PATH = os.environ.get("MMALIFE_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mma_life.db"))


def connect():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def report_balance(conn):
    """Analyze fighter balance — attribute distributions, archetype mix."""
    print("\n=== BALANCE ANALYSIS ===")
    cur = conn.execute("""
        SELECT archetype, COUNT(*) as cnt,
               ROUND(AVG(rank), 1) as avg_rank,
               ROUND(AVG(wins * 1.0), 1) as avg_wins
        FROM fighters WHERE archetype IS NOT NULL
        GROUP BY archetype ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    if rows:
        print("\nArchetype Distribution:")
        for archetype, cnt, avg_rank, avg_wins in rows:
            print(f"  {archetype:20s} {cnt:4d} fighters  avg_rank={avg_rank:5.1f}  avg_wins={avg_wins:4.1f}")

    cur = conn.execute("""
        SELECT weight_class, COUNT(*) as cnt,
               ROUND(AVG(wins), 1) as avg_wins,
               ROUND(AVG(rank), 1) as avg_rank
        FROM fighters WHERE retired = 0
        GROUP BY weight_class ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    if rows:
        print("\nWeight Class Distribution:")
        for wc, cnt, avg_wins, avg_rank in rows:
            print(f"  {wc:20s} {cnt:4d} fighters  avg_wins={avg_wins:4.1f}  avg_rank={avg_rank:5.1f}")

    cur = conn.execute("""
        SELECT COUNT(*) FROM fighters WHERE retired = 1
    """)
    retired = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM fighters")
    total = cur.fetchone()[0]
    print(f"\nRetired: {retired}/{total} ({retired/max(1,total)*100:.0f}%)")


def report_fighters(conn):
    """Report anomalies and extremes in fighter data."""
    print("\n=== FIGHTER ANALYSIS ===")
    cur = conn.execute("""
        SELECT name, weight_class, wins, losses, rank, archetype
        FROM fighters WHERE rank <= 5 AND retired = 0
        ORDER BY weight_class, rank
    """)
    rows = cur.fetchall()
    if rows:
        print("\nTop 5 Ranked Fighters (by weight class):")
        last_wc = ""
        for name, wc, wins, losses, rank, archetype in rows:
            if wc != last_wc:
                print(f"\n  {wc}:")
                last_wc = wc
            print(f"    #{rank} {name:25s} {wins}-{losses} ({archetype})")

    cur = conn.execute("""
        SELECT name, weight_class, wins, losses, rank, win_streak
        FROM fighters WHERE win_streak >= 5 AND retired = 0
        ORDER BY win_streak DESC LIMIT 10
    """)
    rows = cur.fetchall()
    if rows:
        print("\nHot Streaks (5+ wins):")
        for name, wc, wins, losses, rank, streak in rows:
            print(f"  {name:25s} ({wc:15s}) {wins}-{losses} #{rank} — {streak} wins in a row")

    cur = conn.execute("""
        SELECT name, weight_class, wins, losses, rank, rank - peak_rank as decline
        FROM fighters WHERE peak_rank <= 10 AND rank > 20 AND retired = 0
        ORDER BY decline DESC LIMIT 10
    """)
    rows = cur.fetchall()
    if rows:
        print("\nBiggest Declines:")
        for name, wc, wins, losses, rank, decline in rows:
            print(f"  {name:25s} ({wc:15s}) {wins}-{losses} fell {decline} spots")


def report_promotions(conn):
    """Analyze promotion structure."""
    print("\n=== PROMOTION ANALYSIS ===")
    cur = conn.execute("SELECT * FROM promotions")
    rows = cur.fetchall()
    if rows:
        cols = [desc[0] for desc in cur.description]
        print(f"\n{'Name':30s} {'Tier':10s} {'Champions':15s} {'Fighters':10s}")
        print("-" * 70)
        for row in rows:
            d = dict(zip(cols, row))
            champs = json.loads(d.get("champions", "{}"))
            champs_active = sum(1 for v in champs.values() if v)
            try:
                fighter_ids = json.loads(d.get("fighter_ids", "[]"))
            except (json.JSONDecodeError, TypeError):
                fighter_ids = []
            print(f"{d['name']:30s} {d['tier_name']:10s} {champs_active:5d}/{len(champs):5d} champions  {len(fighter_ids):4d} fighters")


def report_careers(conn):
    """Analyze session/career data."""
    print("\n=== CAREER ANALYSIS ===")
    cur = conn.execute("SELECT sid, data, updated_at FROM sessions WHERE sid NOT LIKE '__%'")
    rows = cur.fetchall()
    if rows:
        print(f"\nActive player sessions: {len(rows)}")
        for sid, data_blob, updated in rows:
            try:
                import pickle
                session = pickle.loads(data_blob)
                f = session.get("fighter")
                if f:
                    career = session.get("career")
                    promo = career.current_promotion.name if career and career.current_promotion else "Free Agent"
                    print(f"  {f.name:25s} {f.wins}-{f.losses} ({f.weight_class:15s}) @ {promo}")
            except Exception:
                print(f"  Session {sid[:16]}... (unreadable)")
    else:
        print("No player sessions found.")


def report_world(conn):
    """Analyze world simulation state."""
    print("\n=== WORLD STATE ===")
    cur = conn.execute("SELECT data FROM sessions WHERE sid = '__world_news__'")
    row = cur.fetchone()
    if row:
        try:
            news = json.loads(row[0])
            print(f"\nWorld news items: {len(news)}")
            recent = news[-5:]
            for item in recent:
                if isinstance(item, dict):
                    text = item.get("text", item.get("headline", str(item)[:80]))
                else:
                    text = str(item)[:80]
                print(f"  {text}")
        except Exception:
            print("  News data unreadable")


if __name__ == "__main__":
    report_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    conn = connect()

    if report_type in ("all", "balance"):
        report_balance(conn)
    if report_type in ("all", "fighters"):
        report_fighters(conn)
    if report_type in ("all", "promotions"):
        report_promotions(conn)
    if report_type in ("all", "careers"):
        report_careers(conn)
    if report_type in ("all", "world"):
        report_world(conn)

    conn.close()
    print()
