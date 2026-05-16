"""
MMA Life Simulator — Real-World MMA Stats Fetcher
Fetches and aggregates fight statistics from ufcstats.com.
Supports per-weight-class breakdowns, year filtering, and striking/grappling stats.

Usage:
  python3 stats_fetcher.py                       # Fetch and display stats
  python3 stats_fetcher.py --save                # Save to config/real_stats.json
  python3 stats_fetcher.py --since 2010          # Only events from 2010 onwards
  python3 stats_fetcher.py --since 2010 --save   # Both
  python3 stats_fetcher.py --since 2010 --limit 50 --save  # Limit to first N
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime

BASE_URL = "http://ufcstats.com"
EVENTS_URL = BASE_URL + "/statistics/events/completed?page=all"
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
STATS_FILE = os.path.join(CONFIG_DIR, "real_stats.json")
USER_AGENT = "Mozilla/5.0"

ROW_RE = re.compile(
    r'<tr\s+class="b-fight-details__table-row[^"]*'
    r'b-fight-details__table-row__hover[^"]*'
    r'js-fight-details-click[^"]*"[^>]*>(.*?)</tr>', re.DOTALL
)

# ufcstats.com event page fight table cell mapping (0-indexed, fixed regex):
# 0: W/L flag, 1: Names, 2: KDs, 3: Total STR, 4: TD, 5: SUB, 6: Weight, 7: Method, 8: Round, 9: Time
CELL_KD = 2
CELL_STR = 3
CELL_TD = 4
CELL_SUB = 5
CELL_WEIGHT = 6
CELL_METHOD = 7
CELL_ROUND = 8
CELL_TIME = 9


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] {e}", file=sys.stderr)
        return None


def get_cell_text(row_html, idx):
    cells = re.findall(
        r'<td[^>]*class="[^"]*b-fight-details__table-col[^"]*"[^>]*>(.*?)</td>',
        row_html, re.DOTALL
    )
    if idx < len(cells):
        text = re.sub(r'<[^>]+>', ' ', cells[idx]).strip()
        return re.sub(r'\s+', ' ', text)
    return ""


def parse_fighter_stats_pair(cell_text):
    """Parse space-separated fighter pair like '123 98' or '0 0' into [f1, f2] ints."""
    parts = cell_text.strip().split()
    vals = []
    for p in parts:
        try:
            vals.append(int(p))
        except ValueError:
            vals.append(0)
    while len(vals) < 2:
        vals.append(0)
    return vals[:2]


def extract_event_dates_and_links(html):
    """Extract (date, event_url, event_name) tuples from events listing page."""
    table = re.search(
        r'<table[^>]*class="b-statistics__table-events[^"]*"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not table:
        return []

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table.group(1), re.DOTALL)
    results = []
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 2:
            continue
        text_cell = re.sub(r'<[^>]+>', ' ', cells[0]).strip()
        text_cell = re.sub(r'\s+', ' ', text_cell)

        link_m = re.search(r'href="([^"]*event-details[^"]*)"', cells[0])
        if not link_m:
            continue
        event_url = link_m.group(1)

        date = None
        for m_name, m_num in month_map.items():
            dm = re.search(
                rf'{m_name}\s+(\d+),?\s+(\d{{4}})', text_cell, re.IGNORECASE
            )
            if dm:
                try:
                    date = datetime(int(dm.group(2)), m_num, int(dm.group(1)))
                except ValueError:
                    date = None
                break

        results.append({
            "date": date,
            "url": event_url,
            "name": text_cell[:80],
            "year": date.year if date else None,
        })
    return results


def parse_fights_from_event(html):
    """Parse fight data from an event detail page, including per-fighter stats."""
    fights = []

    for m in ROW_RE.finditer(html):
        row = m.group(1)

        is_winner = bool(re.search(
            r'class="b-flag[^"]*b-flag_style_green[^"]*"', row
        ))

        fighters = re.findall(
            r'<a\s+[^>]*href="[^"]*fighter-details[^"]*"[^>]*>\s*([^<]+?)\s*</a>',
            row
        )
        fighters = [re.sub(r'\s+', ' ', f.strip()) for f in fighters]
        if len(fighters) < 2:
            continue

        method = get_cell_text(row, CELL_METHOD)
        if not method or method.lower() in ("view matchup", ""):
            continue

        rnd_text = get_cell_text(row, CELL_ROUND)
        time_text = get_cell_text(row, CELL_TIME)
        weight_class = get_cell_text(row, CELL_WEIGHT)

        try:
            rnd = int(rnd_text) if rnd_text else 0
        except ValueError:
            rnd = 0

        kd = parse_fighter_stats_pair(get_cell_text(row, CELL_KD))
        total_str = parse_fighter_stats_pair(get_cell_text(row, CELL_STR))
        td = parse_fighter_stats_pair(get_cell_text(row, CELL_TD))
        sub = parse_fighter_stats_pair(get_cell_text(row, CELL_SUB))

        detail = f"{method} | {time_text} | R{rnd}" if rnd else f"{method} | {time_text}"

        fight = {
            "fighter1": fighters[0],
            "fighter2": fighters[1],
            "winner": fighters[0] if is_winner else fighters[1],
            "loser": fighters[1] if is_winner else fighters[0],
            "weight_class": weight_class,
            "method": method,
            "detail": detail[:80],
            "round": rnd,
            "time": time_text,
            "type": classify_method(method, detail),
            "stats": {
                "kd": kd,
                "total_strikes": total_str,
                "takedowns": td,
                "sub_attempts": sub,
            }
        }
        fights.append(fight)

    return fights


def classify_method(method, details):
    """Classify a fight result into a finish type."""
    m = (method + " " + details).lower()

    if "draw" in m:
        return "Draw"
    if "dec" in method.lower() or "decision" in m or "unanimous" in m or \
       "split" in m or "majority" in m:
        return "Decision"
    if method[:3].upper() == "SUB" or "submission" in m or \
       any(w in m for w in ["armbar", "choke", "kimura", "triangle", "lock"]):
        return "Submission"
    if "ko/tko" in method.lower() or "tko" in method.lower() or \
       "ko" in method[:4].upper():
        if "doctor" in m:
            return "TKO (Doctor Stoppage)"
        return "TKO"
    return method.split("(")[0].strip() if method else "Unknown"


def estimate_fight_seconds(rnd, time_str):
    """Estimate total fight duration in seconds."""
    if not rnd or rnd == 0:
        return 900
    minutes = 0
    seconds = 0
    tm = re.match(r'(\d+):(\d+)', time_str)
    if tm:
        minutes = int(tm.group(1))
        seconds = int(tm.group(2))
    full_rounds = rnd - 1
    return full_rounds * 300 + (300 - (minutes * 60 + seconds))


def per_weight_class_aggregate(fights):
    """Aggregate stats by weight class and overall."""
    by_wc = defaultdict(list)
    for f in fights:
        wc = f.get("weight_class", "Unknown") or "Unknown"
        by_wc[wc].append(f)

    def _agg(fight_list):
        total = len(fight_list)
        if total == 0:
            return None

        ft = Counter()
        rd = Counter()
        total_strikes_f1 = 0
        total_strikes_f2 = 0
        total_takedowns_f1 = 0
        total_takedowns_f2 = 0
        total_kd_f1 = 0
        total_kd_f2 = 0
        total_sub_att_f1 = 0
        total_sub_att_f2 = 0
        total_est_seconds = 0

        for f in fight_list:
            ft[f.get("type", "Unknown")] += 1
            rd[f.get("round", 0)] += 1
            s = f.get("stats", {})
            total_strikes_f1 += s.get("total_strikes", [0, 0])[0]
            total_strikes_f2 += s.get("total_strikes", [0, 0])[1]
            total_takedowns_f1 += s.get("takedowns", [0, 0])[0]
            total_takedowns_f2 += s.get("takedowns", [0, 0])[1]
            total_kd_f1 += s.get("kd", [0, 0])[0]
            total_kd_f2 += s.get("kd", [0, 0])[1]
            total_sub_att_f1 += s.get("sub_attempts", [0, 0])[0]
            total_sub_att_f2 += s.get("sub_attempts", [0, 0])[1]
            total_est_seconds += estimate_fight_seconds(
                f.get("round", 0), f.get("time", "5:00")
            )

        tko = ft.get("TKO", 0) + ft.get("TKO (Doctor Stoppage)", 0)
        sub = ft.get("Submission", 0)
        dec = ft.get("Decision", 0) + ft.get("Draw", 0)
        total_minutes = total_est_seconds / 60.0

        return {
            "total_fights": total,
            "ko_tko": ft.get("TKO", 0),
            "tko_doctor": ft.get("TKO (Doctor Stoppage)", 0),
            "submission": sub,
            "decision": dec,
            "draw": ft.get("Draw", 0),
            "unknown": ft.get("Unknown", 0),
            "ko_tko_pct": round(tko / total * 100, 1),
            "submission_pct": round(sub / total * 100, 1),
            "decision_pct": round(dec / total * 100, 1),
            "finish_pct": round((tko + sub) / total * 100, 1),
            "tko_sub_ratio": round(tko / max(1, sub), 2),
            "round_distribution": {
                str(k): round(v / total * 100, 1)
                for k, v in sorted(rd.items())
            },
            "avg_total_strikes_per_fight": round(
                (total_strikes_f1 + total_strikes_f2) / total, 1
            ),
            "avg_total_strikes_per_min": round(
                (total_strikes_f1 + total_strikes_f2) / max(1, total_minutes), 2
            ),
            "avg_takedowns_per_fight": round(
                (total_takedowns_f1 + total_takedowns_f2) / total, 2
            ),
            "avg_kd_per_fight": round(
                (total_kd_f1 + total_kd_f2) / total, 2
            ),
            "avg_sub_attempts_per_fight": round(
                (total_sub_att_f1 + total_sub_att_f2) / total, 2
            ),
            "avg_fight_duration_seconds": round(
                total_est_seconds / total, 1
            ),
            "strikes_per_takedown": round(
                (total_strikes_f1 + total_strikes_f2) /
                max(1, total_takedowns_f1 + total_takedowns_f2), 1
            ),
            "takedown_rate": round(
                (total_takedowns_f1 + total_takedowns_f2) / total * 100 /
                max(1, (total_est_seconds / 60)), 2
            ),
        }

    result = {}
    for wc in sorted(by_wc.keys()):
        agg = _agg(by_wc[wc])
        if agg:
            result[wc] = agg

    all_fights = sum(by_wc.values(), [])
    overall = _agg(all_fights)
    return {"by_weight_class": result, "overall": overall}


def print_stats(data):
    overall = data.get("overall")
    if not overall:
        return

    t = overall["total_fights"]
    print(f"\n{'='*55}")
    print(f"  {'UFC REAL-WORLD FIGHT STATISTICS':^51}")
    print(f"{'='*55}")
    print(f"  Total fights analyzed: {t}")
    print(f"\n  {'Finish Rates':>40}")
    print(f"  {'─'*51}")
    print(f"  KO/TKO:              {overall['ko_tko_pct']:>6.1f}%  ({overall['ko_tko']}/{t})")
    print(f"    └─ Doctor stoppage: {overall['tko_doctor']:>4} fights")
    print(f"  Submission:          {overall['submission_pct']:>6.1f}%  ({overall['submission']}/{t})")
    print(f"  Decision:            {overall['decision_pct']:>6.1f}%  ({overall['decision']}/{t})")
    print(f"  Finish total:        {overall['finish_pct']:>6.1f}%")
    print(f"  TKO/Sub ratio:       {overall['tko_sub_ratio']:>6.2f}")

    print(f"\n  {'Striking & Grappling':>40}")
    print(f"  {'─'*51}")
    print(f"  Avg strikes landed/fight:  {overall['avg_total_strikes_per_fight']:>7.1f}")
    print(f"  Avg strikes landed/min:    {overall['avg_total_strikes_per_min']:>7.2f}")
    print(f"  Avg takedowns/fight:       {overall['avg_takedowns_per_fight']:>7.2f}")
    print(f"  Avg KD/fight:              {overall['avg_kd_per_fight']:>7.2f}")
    print(f"  Avg sub attempts/fight:    {overall['avg_sub_attempts_per_fight']:>7.2f}")
    print(f"  Avg fight duration:        {overall['avg_fight_duration_seconds']:>7.1f}s")
    print(f"  Strikes per takedown:      {overall['strikes_per_takedown']:>7.1f}")

    print(f"\n  {'Round Distribution':>37}")
    print(f"  {'─'*51}")
    for r_str, pct in sorted(
        overall["round_distribution"].items(), key=lambda x: int(x[0])
    ):
        p = float(pct) / 100 * t
        bar = "█" * max(1, int(pct / 2))
        print(f"  Round {r_str}: {int(p):>5}/{t} ({pct:>5.1f}%) {bar}")

    if data.get("by_weight_class"):
        print(f"\n  {'Per Weight Class KO/TKO%':>40}")
        print(f"  {'─'*51}")
        for wc, wd in sorted(data["by_weight_class"].items()):
            if wc == "Open Weight" or wc == "Unknown":
                continue
            print(f"  {wc:25s}  {wd['ko_tko_pct']:>5.1f}%  "
                  f"Sub {wd['submission_pct']:>4.1f}%  "
                  f"Dec {wd['decision_pct']:>4.1f}%  "
                  f"({wd['total_fights']:>4} fights)")


def save_stats(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    overall = data.get("overall", {})
    t = overall.get("total_fights", 0)

    targets = {
        "source": "ufcstats.com (via stats_fetcher.py)",
        "fetched_at": datetime.now().isoformat(),
        "total_fights_analyzed": t,
        "real_world_rates": {
            "ko_tko_pct": overall.get("ko_tko_pct", 0),
            "submission_pct": overall.get("submission_pct", 0),
            "decision_pct": overall.get("decision_pct", 0),
            "finish_pct": overall.get("finish_pct", 0),
        },
        "striking_grappling": {
            "avg_total_strikes_per_min": overall.get("avg_total_strikes_per_min", 0),
            "avg_takedowns_per_fight": overall.get("avg_takedowns_per_fight", 0),
            "avg_kd_per_fight": overall.get("avg_kd_per_fight", 0),
            "avg_sub_attempts_per_fight": overall.get("avg_sub_attempts_per_fight", 0),
            "strikes_per_takedown": overall.get("strikes_per_takedown", 0),
        },
        "per_weight_class": {},
        "balance_targets": {}
    }

    for wc, wd in sorted(data.get("by_weight_class", {}).items()):
        targets["per_weight_class"][wc] = {
            "ko_tko_pct": wd.get("ko_tko_pct", 0),
            "submission_pct": wd.get("submission_pct", 0),
            "decision_pct": wd.get("decision_pct", 0),
            "finish_pct": wd.get("finish_pct", 0),
            "avg_total_strikes_per_min": wd.get("avg_total_strikes_per_min", 0),
            "avg_takedowns_per_fight": wd.get("avg_takedowns_per_fight", 0),
            "avg_sub_attempts_per_fight": wd.get("avg_sub_attempts_per_fight", 0),
            "total_fights": wd.get("total_fights", 0),
            "round_distribution": wd.get("round_distribution", {}),
            "avg_fight_duration_seconds": wd.get("avg_fight_duration_seconds", 0),
        }

        ft = wd.get("total_fights", 0)
        if ft > 0:
            targets["balance_targets"][wc] = {
                "even_3_round": {
                    "KO_TKO_target": wd.get("ko_tko_pct", 0),
                    "Submission_target": wd.get("submission_pct", 0),
                    "Decision_target": wd.get("decision_pct", 0),
                },
                "even_5_round_title": {
                    "KO_TKO_target": round(wd.get("ko_tko_pct", 0) * 0.85, 1),
                    "Submission_target": wd.get("submission_pct", 0),
                    "Decision_target": round(min(100, wd.get("decision_pct", 0) * 1.35), 1),
                },
            }

    with open(STATS_FILE, "w") as f:
        json.dump(targets, f, indent=2)
    print(f"\nSaved real stats and balance targets → {STATS_FILE}")


def fetch_data(since_year=None, limit=None, save=False):
    print("=== MMA REAL-WORLD STATS FETCHER ===")
    print(f"Source: {EVENTS_URL}")

    html = fetch(EVENTS_URL)
    if not html:
        print("ERROR: Could not fetch events page.")
        return None

    events = extract_event_dates_and_links(html)
    print(f"Found {len(events)} completed events")

    if since_year:
        filtered = [e for e in events if e["year"] and e["year"] >= since_year]
        print(f"  Filtering to {since_year}+: {len(filtered)} events")
        events = filtered

    events.sort(key=lambda e: e["date"] or datetime.min, reverse=True)

    if limit:
        events = events[:limit]
        print(f"  Limiting to first {limit} events")

    all_fights = []
    fetched = 0
    failed = 0
    unknown_count = 0

    for i, ev in enumerate(events):
        year_str = str(ev["year"]) if ev["year"] else "????"
        name = ev["name"]
        print(f"  [{i+1}/{len(events)}] ({year_str}) {name[:60]}...", end=" ", flush=True)

        page = fetch(ev["url"])
        if page:
            fights = parse_fights_from_event(page)
            all_fights.extend(fights)
            fetched += 1
            uk = sum(1 for f in fights if f.get("type") == "Unknown")
            unknown_count += uk
            sig = sum(1 for f in fights if f.get("type") not in ("Unknown",))
            print(f"{len(fights)} fights ({sig} classified)" +
                  (f" [{uk} unknown]" if uk else ""))
        else:
            failed += 1
            print("failed")

    print(f"\nFetched: {fetched} events, {failed} failed, "
          f"{len(all_fights)} total fights "
          f"({unknown_count} unknown)")

    if not all_fights:
        return None

    data = per_weight_class_aggregate(all_fights)
    if data and data.get("overall"):
        data["total_events"] = fetched
        data["total_fights_raw"] = len(all_fights)

    return data


if __name__ == "__main__":
    start = time.time()
    since_year = None
    limit = None
    save = False

    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--save":
            save = True
        elif a.startswith("--since="):
            since_year = int(a.split("=")[1])
        elif a == "--since" and i + 1 < len(args):
            since_year = int(args[i + 1])
        elif a.startswith("--limit="):
            limit = int(a.split("=")[1])
        elif a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    data = fetch_data(since_year=since_year, limit=limit, save=save)
    if data:
        print_stats(data)
        if save:
            save_stats(data)

    print(f"\nCompleted in {time.time() - start:.1f}s")
