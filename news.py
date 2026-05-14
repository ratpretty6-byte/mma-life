from typing import Dict, List, Optional
import random

def format_news_item(item: Dict) -> Dict:
    news_type = item.get("type", "unknown")
    formatters = {
        "fight_result": _format_fight_result,
        "fighter_signing": _format_signing,
        "retirement": _format_retirement,
        "comeback": _format_comeback,
        "rivalry": _format_rivalry,
        "title_change": _format_title_change,
        "injury_report": _format_injury,
        "training_update": _format_training,
        "press_conference": _format_press_conference,
        "scandal": _format_scandal,
        "award": _format_award,
        "title_stripped": _format_title_stripped,
        "prospect": _format_prospect,
        "replenish": _format_replenish,
    }
    formatter = formatters.get(news_type, _format_unknown)
    result = formatter(item)
    result["type"] = news_type
    return result

def _format_unknown(item: Dict) -> Dict:
    return {"headline": "Unknown event", "body": "", "severity": "routine"}

def _get_editorial_tone(fighter_image: str = "neutral") -> str:
    if fighter_image == "hero":
        return random.choice(["acclaimed", "beloved", "fan-favorite"])
    elif fighter_image == "villain":
        return random.choice(["controversial", "polarizing", "dreaded"])
    return ""

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
        method_detail = item.get("method", "Draw")
        if "Unanimous" in method_detail:
            headline = f"{f1} vs {f2} plays out to a Unanimous Draw"
            body = f"{tag} {wc} bout at {p}: All three judges scored it even. Neither fighter could separate themselves."
        elif "Majority" in method_detail:
            headline = f"{f1} vs {f2} ends in a Majority Draw"
            body = f"{tag} {wc} bout at {p}: Two judges saw it even, one had a split opinion. Rare!"
        else:
            headline = f"{f1} vs {f2} fight to a Split Draw"
            body = f"{tag} {wc} bout at {p}: The judges couldn't agree — a split draw."
        return {"headline": headline, "body": body, "severity": "routine"}

    method_short = method.replace("TKO", "TKO").replace("KO", "KO").replace("Submission", "sub")
    if "(" in method_short:
        method_short = method_short.split("(")[0].strip()

    if "Split" in method:
        headline = f"SPLIT DECISION! {winner} edges {loser}!"
        body = f"{tag} {wc} bout at {p}: {winner} takes a split decision over {loser}. Two judges saw it for {winner}, one disagreed."
        severity = "major" if rnd >= 3 else "routine"
    elif "Majority" in method:
        headline = f"Majority Decision: {winner} gets the nod over {loser}"
        body = f"{tag} {wc} bout at {p}: {winner} wins a majority decision. Two judges favored {winner}, one called it even."
        severity = "routine"
    elif is_title and title_changed:
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
    if item.get("controversial"):
        body += " The result has been met with controversy."

    rnd_info = item.get("rivalry_info")
    if rnd_info:
        body += f" This fight adds another chapter to their growing rivalry."

    return {"headline": headline, "body": body, "severity": severity}

def _format_signing(item: Dict) -> Dict:
    fighter = item.get("fighter", "Unknown")
    promo = item.get("promotion", "a promotion")
    tier = item.get("tier", "")
    tag = f"[{tier}]" if tier else ""
    headline = f"{fighter} signs with {promo}"
    body = f"{tag} {fighter} has signed a multi-fight contract with {promo}. A new chapter begins."
    return {"headline": headline, "body": body, "severity": "routine"}

def _format_retirement(item: Dict) -> Dict:
    fighter = item.get("fighter", "Unknown")
    age = item.get("age", "?")
    record = item.get("record", "?")
    legend = item.get("legacy_score", 0)
    if legend > 80:
        headline = f"LEGEND RETIRES! {fighter} hangs up the gloves!"
        body = f"At age {age}, {fighter} ({record}) calls it a career. A future Hall of Famer."
        severity = "major"
    elif legend > 50:
        headline = f"{fighter} announces retirement"
        body = f"After a solid career ({record}), {fighter} retires at age {age}."
        severity = "routine"
    else:
        headline = f"{fighter} steps away from the sport"
        body = f"{fighter} ({record}) retires at age {age}."
        severity = "routine"
    return {"headline": headline, "body": body, "severity": severity}

def _format_comeback(item: Dict) -> Dict:
    fighter = item.get("fighter", "Unknown")
    years_out = item.get("years_out", 0)
    headline = f"COMEBACK! {fighter} returns to the octagon!"
    body = f"After {years_out} years away, {fighter} has announced they are unretiring."
    return {"headline": headline, "body": body, "severity": "major"}

def _format_rivalry(item: Dict) -> Dict:
    f1 = item.get("fighter1", "?")
    f2 = item.get("fighter2", "?")
    intensity = item.get("intensity", 0)
    fight_count = item.get("fight_count", 1)
    if fight_count >= 3:
        headline = f"TRILOGY! {f1} and {f2} set for rubber match!"
        body = f"These two warriors have fought {fight_count} times. The rivalry reaches boiling point."
    elif intensity > 0.7:
        headline = f"BAD BLOOD: {f1} and {f2} exchange words"
        body = f"The tension between {f1} and {f2} is at an all-time high. Someone has to give."
    else:
        headline = f"Rivalry brewing: {f1} vs {f2}"
        body = f"A new rivalry is taking shape between {f1} and {f2}."
    return {"headline": headline, "body": body, "severity": "major" if fight_count >= 3 else "routine"}

def _format_title_change(item: Dict) -> Dict:
    champ = item.get("champion", "?")
    wc = item.get("weight_class", "?")
    promo = item.get("promotion", "?")
    headline = f"🏆 {champ} crowned {wc} champion!"
    body = f"{champ} is the new {wc} champion at {promo}."
    return {"headline": headline, "body": body, "severity": "major"}

def _format_injury(item: Dict) -> Dict:
    fighter = item.get("fighter", "?")
    injury_type = item.get("injury_type", "injury")
    recovery = item.get("recovery_days", 0)
    headline = f"{fighter} sidelined with {injury_type}"
    body = f"{fighter} suffered a {injury_type} and is expected to miss {recovery} days."
    severity = "major" if recovery > 30 else "routine"
    return {"headline": headline, "body": body, "severity": severity}

def _format_training(item: Dict) -> Dict:
    fighter = item.get("fighter", "?")
    gym = item.get("gym", "a gym")
    headline = f"{fighter} puts in work at {gym}"
    body = f"{fighter} was spotted training at {gym}, preparing for their next challenge."
    return {"headline": headline, "body": body, "severity": "routine"}

def _format_press_conference(item: Dict) -> Dict:
    fighter = item.get("fighter", "?")
    tone = item.get("tone", "respectful")
    opponent = item.get("opponent", "?")
    if tone == "trash_talk":
        headline = f"HEATED! {fighter} goes off on {opponent} at presser!"
        body = f"{fighter} didn't hold back at today's press conference, taking shots at {opponent}."
    elif tone == "staredown":
        headline = f"INTENSE staredown between {fighter} and {opponent}"
        body = f"The faceoff between {fighter} and {opponent} was electric. The crowd erupted."
    else:
        headline = f"{fighter} and {opponent} show respect ahead of clash"
        body = f"Both fighters kept it professional at today's press conference."
    return {"headline": headline, "body": body, "severity": "routine"}

def _format_scandal(item: Dict) -> Dict:
    fighter = item.get("fighter", "?")
    scandal_type = item.get("scandal_type", "controversy")
    headline = f"SCANDAL: {fighter} involved in {scandal_type}"
    body = f"{fighter} is at the center of a {scandal_type} controversy. The promotion is investigating."
    return {"headline": headline, "body": body, "severity": "major"}

def _format_award(item: Dict) -> Dict:
    award = item.get("award", "Fighter of the Year")
    winner = item.get("winner", "?")
    headline = f"{winner} wins {award}!"
    body = f"{winner} has been awarded {award} for their outstanding achievements."
    return {"headline": headline, "body": body, "severity": "major"}

def _format_title_stripped(item: Dict) -> Dict:
    fighter = item.get("fighter", "?")
    new_champ = item.get("new_champion", "?")
    headline = f"BELT VACATED! {fighter} stripped of title!"
    body = f"{fighter} has been stripped of the title due to inactivity. {new_champ} has been elevated to champion."
    return {"headline": headline, "body": body, "severity": "major"}

def _format_prospect(item: Dict) -> Dict:
    fighter = item.get("fighter", "?")
    age = item.get("age", "?")
    wc = item.get("weight_class", "?")
    promo = item.get("promotion", "?")
    headline = f"New prospect alert: {fighter} enters the {wc} division!"
    body = f"A new {age}-year-old prospect, {fighter}, has signed with {promo}. One to watch in the {wc} division."
    return {"headline": headline, "body": body, "severity": "routine"}

def _format_replenish(item: Dict) -> Dict:
    promo = item.get("promotion", "?")
    wc = item.get("weight_class", "?")
    count = item.get("count", 0)
    headline = f"{count} new fighters join {promo}'s {wc} division"
    body = f"{promo} has signed {count} new fighters to bolster their {wc} roster."
    return {"headline": headline, "body": body, "severity": "routine"}


class StorylineTracker:
    def __init__(self):
        self.storylines: Dict[str, Dict] = {}

    def track_rivalry(self, f1_name: str, f2_name: str, fight_count: int, intensity: float) -> Optional[Dict]:
        key = f"rivalry_{min(f1_name, f2_name)}_{max(f1_name, f2_name)}"
        if key not in self.storylines:
            self.storylines[key] = {
                "type": "rivalry", "fighter1": f1_name, "fighter2": f2_name,
                "fight_count": 0, "intensity": 0.0, "chapter": 0,
            }
        sl = self.storylines[key]
        sl["fight_count"] = fight_count
        sl["intensity"] = intensity
        sl["chapter"] += 1
        if fight_count >= 3 and sl["chapter"] == 3:
            return {
                "type": "rivalry", "fighter1": f1_name, "fighter2": f2_name,
                "intensity": intensity, "fight_count": fight_count,
            }
        elif fight_count >= 2 and sl["chapter"] == 2:
            return {
                "type": "rivalry", "fighter1": f1_name, "fighter2": f2_name,
                "intensity": intensity, "fight_count": fight_count,
            }
        if intensity > 0.7 and sl["chapter"] == 1:
            return {
                "type": "rivalry", "fighter1": f1_name, "fighter2": f2_name,
                "intensity": intensity, "fight_count": fight_count,
            }
        return None


def format_news_items(items: List[Dict], limit: int = 50) -> List[Dict]:
    formatted = []
    for item in items[-limit:]:
        formatted.append(format_news_item(item))
    return list(reversed(formatted))
