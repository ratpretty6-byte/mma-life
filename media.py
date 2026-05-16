import random
from datetime import datetime
from typing import Dict, List

from fighter import Fighter


class MediaSystem:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.popularity = 50.0
        self.public_image = "neutral"
        self.social_followers = 1000
        self.media_obligations: List[Dict] = []
        self.fan_engagement = 0.5

    def update_popularity(self, delta: float):
        self.popularity = max(0.0, min(100.0, self.popularity + delta))
        self.fighter.attributes["charisma"] = int(
            self.popularity * 0.8 + self.fighter.attributes["charisma"] * 0.2
        )

    def set_public_image(self, image: str):
        if image in ["hero", "villain", "neutral"]:
            self.public_image = image
            self.update_popularity(5.0 if image == "hero" else (-3.0 if image == "villain" else 0))

    def add_obligation(self, event_type: str, date: datetime, bonus: float = 0.0):
        self.media_obligations.append({
            "type": event_type,
            "date": date,
            "bonus": bonus,
            "completed": False
        })

    def complete_obligation(self, obligation: Dict):
        if obligation in self.media_obligations and not obligation["completed"]:
            obligation["completed"] = True
            self.update_popularity(obligation["bonus"])
            self.social_followers += int(obligation["bonus"] * 100)
            self.fan_engagement = min(1.0, self.fan_engagement + 0.1)

    def post_social(self, content_type: str) -> float:
        gains = {
            "training_update": 1.0,
            "trash_talk": 2.0 if self.public_image == "villain" else -1.0,
            "charity": 3.0 if self.public_image == "hero" else 1.0,
            "fight_announcement": 5.0
        }
        gain = gains.get(content_type, 0.0)
        self.update_popularity(gain)
        self.social_followers += int(gain * 50)
        return gain

    def do_press_conference(self, opponent: Fighter, rivalry_intensity: float = 0.0) -> Dict:
        options = ["respectful", "trash_talk", "staredown"]
        weights = [0.3, 0.4, 0.3]
        if rivalry_intensity > 0.5:
            weights = [0.1, 0.6, 0.3]
        choice = random.choices(options, weights=weights)[0]

        result = f"Press conference: {self.fighter.name} vs {opponent.name} - "
        pop_gain = 0
        if choice == "respectful":
            result += "Both fighters show mutual respect."
            pop_gain = 1.0
            self.set_public_image("hero")
        elif choice == "trash_talk":
            result += f"{self.fighter.name} gets in {opponent.name}'s face! Heated exchange!"
            pop_gain = 3.0
            self.fighter.attributes["composure"] = max(0, self.fighter.attributes["composure"] - 2)
        elif choice == "staredown":
            result += "Intense staredown! The crowd is going wild!"
            pop_gain = 2.0

        self.update_popularity(pop_gain)
        self.social_followers += int(pop_gain * 100)
        return {"action": choice, "text": result, "popularity_gain": pop_gain}

    def do_open_workout(self) -> Dict:
        pop_gain = random.uniform(0.5, 1.5)
        self.update_popularity(pop_gain)
        texts = [
            f"{self.fighter.name} puts on a show at open workouts!",
            f"Sharp performance from {self.fighter.name} in front of the media.",
            f"{self.fighter.name} looks in incredible shape at the workout.",
        ]
        return {"text": random.choice(texts), "popularity_gain": pop_gain}

    def do_interview(self) -> Dict:
        pop_gain = random.uniform(0.3, 0.8)
        self.update_popularity(pop_gain)
        self.fan_engagement = min(1.0, self.fan_engagement + 0.05)
        texts = [
            f"{self.fighter.name} gives a candid interview.",
            f"Great interview with {self.fighter.name}, talking about the upcoming fight.",
        ]
        return {"text": random.choice(texts), "popularity_gain": pop_gain}

    def get_summary(self) -> Dict:
        return {
            "popularity": self.popularity,
            "public_image": self.public_image,
            "social_followers": self.social_followers,
            "fan_engagement": self.fan_engagement,
            "pending_obligations": len([o for o in self.media_obligations if not o["completed"]])
        }
