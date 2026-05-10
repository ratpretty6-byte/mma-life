from typing import Dict, List

def format_news_item(item: Dict) -> Dict:
    news_type = item.get("type", "unknown")
    if news_type == "fight_result":
        return _format_fight_result(item)
    return {"headline": "Unknown event", "body": "", "severity": "routine"}

def _format_fight_result(item: Dict) -> Dict:
    p = item.get("promotion", "Unknown")
    t = item.get("promotion_tier", "")
    wc = item.get("weight_class", "")
    f1 = item.get("fighter1", "?")
    f2 = item.get("fighter2", "?")
    winner = item.get("winner", "?")
    loser = item.get("loser")
    method = item.get("method", "?")
    rnd = item.get("round", 0)
    upset = item.get("was_upset", False)
    title_changed = item.get("title_changed", False)
    is_title = item.get("is_title_fight", False)
    injury = item.get("injury")
    tag = f"[{t}]" if t else ""
    champ_prefix = "🏆 " if is_title else ""

    if winner == "Draw":
        headline = f"{champ_prefix}{f1} vs {f2} ends in a Draw"
        body = f"{tag} {wc} bout at {p}: Neither fighter could separate themselves on the scorecards."
        return {"headline": headline, "body": body, "severity": "routine"}

    method_short = method.replace("TKO", "TKO").replace("KO", "KO").replace("Submission", "sub")
    if "(" in method_short:
        method_short = method_short.split("(")[0].strip()

    if is_title and title_changed:
        headline = f"🏆 NEW CHAMPION! {winner} dethrones {loser}!"
        body = f"{tag} {wc} title fight: {winner} defeats {loser} by {method_short} in round {rnd} at {p}."
        severity = "major"
    elif is_title:
        headline = f"🏆 {winner} defends {wc} title"
        body = f"{tag} {wc} champion {winner} retains the belt, defeating {loser} by {method_short} in round {rnd}."
        severity = "major"
    elif upset:
        headline = f"UPSET! {winner} shocks {loser}!"
        body = f"{tag} {wc} bout at {p}: Underdog {winner} defeats {loser} by {method_short} in round {rnd}."
        severity = "major"
    else:
        headline = f"{winner} defeats {loser}"
        body = f"{tag} {wc} bout at {p}: {winner} wins by {method_short} in round {rnd}."
        severity = "routine"

    if injury:
        body += f" {loser} suffered a {injury['type']} ({injury['recovery_days']} day recovery)."

    return {"headline": headline, "body": body, "severity": severity}

def format_news_items(items: List[Dict], limit: int = 50) -> List[Dict]:
    formatted = []
    for item in items[-limit:]:
        formatted.append(format_news_item(item))
    return list(reversed(formatted))
