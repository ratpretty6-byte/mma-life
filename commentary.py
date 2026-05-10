import random
from typing import Dict, List, Optional
from fighter import Fighter
from positions import PositionSystem, Position

BACKGROUND_ENTRANCES = {
    "muay_thai": [
        "{fighter} performs the Wai Kru ritual, slow and deliberate, honoring their trainers before battle.",
        "{fighter} wraps their hands and shadow dances to the center, the Muay Thai rhythm on full display.",
        "{fighter} kicks the air with sharp snapping teeps, the crowd feeling the intensity.",
    ],
    "boxing": [
        "{fighter} bounces in on the balls of their feet, hands loose at their sides, a boxer's swagger.",
        "{fighter} shadowboxes their way to the cage, sharp combinations cutting through the air.",
        "{fighter} rolls their shoulders and flashes a confident grin, moving like a seasoned pugilist.",
    ],
    "bjj": [
        "{fighter} moves with deliberate grace, fluid as water, a jiu-jitsu competitor's calm focus.",
        "{fighter} touches the mat and crosses themselves, then methodically works through a movement flow.",
        "{fighter} shuts their eyes for a moment, breathing deeply, visualizing the submissions to come.",
    ],
    "wrestling": [
        "{fighter} storms to the cage with an intense stare, hands ready to clinch and grind.",
        "{fighter} bounces on their toes, low stance, hands probing — a wrestler's posture.",
        "{fighter} slaps their own headgearless head and locks eyes with their opponent, ready for war.",
    ],
    "judo": [
        "{fighter} steps onto the canvas with a measured, purposeful stride, gripping imaginary sleeves.",
        "{fighter} circles with a wide base, hands low, looking for that explosive hip toss.",
        "{fighter} adjusts their gi-less collar grip habitually, the judoka instincts surfacing.",
    ],
    "taekwondo": [
        "{fighter} flashes a quick spinning hook kick in the air during their entrance — pure showmanship.",
        "{fighter} moves with explosive lightness, bouncing and switching stances, a TKD arsenal on display.",
        "{fighter} snaps a high kick over their opponent's head during the staredown, sending a message.",
    ],
    "karate": [
        "{fighter} assumes a bladed stance, hands in position, the precision of a karateka evident.",
        "{fighter} glides to the cage with zen-like focus, each step deliberate and balanced.",
        "{fighter} bows before entering, then snaps into a fighting stance, poised and dangerous.",
    ],
    "sambo": [
        "{fighter} marches forward with a Soviet-era intensity, blending wrestling and submissions.",
        "{fighter} rolls their neck and cracks their knuckles, the combat sambo pedigree showing.",
        "{fighter} circles aggressively, hands reaching for a collar tie, looking for the throw.",
    ],
    "kickboxing": [
        "{fighter} fires a burst of combinations at the air, head movement sharp, ready to trade.",
        "{fighter} bounces in with European kickboxing precision, low kicks chambered and ready.",
        "{fighter} touches gloves and immediately finds their range, a kickboxer's distance.",
    ],
    "capoeira": [
        "{fighter} gingas into the cage, swaying rhythmically, the capoeirista's unpredictable movement on display.",
        "{fighter} cartwheels into their corner, drawing gasps from the crowd — this is entertainment!",
        "{fighter} seems to dance as they enter, but the sharpness in their eyes says this is no game.",
    ],
    "mma": [
        "{fighter} walks in with a well-rounded confidence, comfortable wherever this fight goes.",
        "{fighter} enters the cage with the balanced poise of a true mixed martial artist.",
    ],
}

PERSONALITY_REACTIONS_WIN = {
    "charismatic": [
        "{fighter} raises their arms and works the crowd, eating up the moment with natural star power!",
        "{fighter} grabs the mic: 'I want the biggest fights! Give me anyone they put in front of me!'",
        "{fighter} points to the champion in the crowd — the message is clear: 'I'm coming for you.'",
    ],
    "intimidating": [
        "{fighter} stares through {opponent} as they lay on the canvas, no mercy in their eyes.",
        "{fighter} snarls at the camera and draws a finger across their throat. Chilling.",
        "{fighter} doesn't celebrate — just walks to the center of the cage and calls for the next body.",
    ],
    "cocky": [
        "{fighter} smirks and shrugs: 'That was nothing. I told you all I'm different.'",
        "{fighter} laughs off the challenge, already talking about who they want next.",
        "{fighter} flexes for the crowd and shouts, 'WHO'S NEXT?!' with a cocky grin.",
    ],
    "humble": [
        "{fighter} helps {opponent} to their feet and raises their hand — class act.",
        "{fighter} kneels and says a quiet prayer before celebrating with their team.",
        "{fighter} nods respectfully at their fallen opponent: 'He's a warrior, it was an honor.'",
    ],
    "quiet": [
        "{fighter} simply raises their hand and walks to the corner, letting the result speak.",
        "{fighter} doesn't shout or celebrate — just a quiet nod, then back to the locker room.",
        "{fighter} breathes deeply, the emotion hidden beneath a stoic exterior.",
    ],
    "savage": [
        "{fighter} spits towards the camera: 'That's what happens when you step in here with me.'",
        "{fighter} looms over the fallen {opponent} and shouts, 'GET UP! I'M NOT DONE WITH YOU!'",
        "{fighter} shoves the interviewer aside and screams into the camera with primal intensity.",
    ],
}

PERSONALITY_REACTIONS_LOSS = {
    "humble": [
        "{fighter} nods stoically, accepting defeat with grace. 'He was the better man tonight.'",
        "{fighter} takes a moment to compose themselves, then claps for their victorious opponent.",
    ],
    "cocky": [
        "{fighter} shakes their head in disbelief, refusing to accept the result.",
        "{fighter} storms out of the cage without congratulating their opponent.",
    ],
    "quiet": [
        "{fighter} sits in their corner, head down, processing the loss in silence.",
        "{fighter} stares at the ceiling, the weight of defeat hitting them silently.",
    ],
    "default": [
        "{fighter} walks dejectedly back to their corner, tasting defeat for the first time in a while.",
        "{fighter} drops to a knee, the reality of the loss sinking in.",
    ],
}

PREFIGHT_STREAK_TEMPLATES = [
    "And let's talk about these two warriors! {f1} is {streak1}, while {f2} is {streak2}!",
    "We've got a fascinating matchup here — {f1}, {streak1}, takes on {f2}, {streak2}!",
    "The form guide tells an interesting story: {f1} is {streak1}, and {f2} is {streak2}!",
    "What a fascinating clash of momentum! {f1}, {streak1}, faces {f2}, {streak2}!",
]

PREFIGHT_RIVALRY_TEMPLATES = [
    "These two have HISTORY! In their first meeting, {detail}",
    "The rematch we've all been waiting for! {detail}",
    "This is a personal grudge match! {detail}",
    "There's bad blood here! {detail}",
]

PREFIGHT_MATCHUP_TEMPLATES = [
    "This is a {difficulty} for {lower_ranked_fighter}, who's facing a serious step up in competition!",
    "A {difficulty} matchup on paper — {f1}'s {style1} against {f2}'s {style2}!",
    "The {rank_info} — this has all the makings of a classic!",
    "Stylistically, this is fascinating! {f1} wants to {goal1}, while {f2} wants to {goal2}!",
]

class CommentaryEngine:
    def __init__(self):
        self.strike_templates = {
            "standing": [
                "{attacker} lands a clean {strike_type} on {defender}'s {target}!",
                "{defender} eats a big {strike_type} from {attacker}!",
                "{attacker} snaps {defender}'s head back with a {strike_type}!",
                "{defender} blocks the {strike_type} but still takes some damage.",
                "{attacker} fires a {strike_type} that finds its mark on {target}!",
                "Sharp {strike_type} from {attacker} catches {defender} coming in!",
                "{attacker} stings {defender} with a quick {strike_type} to the {target}!",
                "{defender} gets touched up by a {strike_type} from {attacker}!",
                "Crisp {strike_type} from {attacker}! {defender} felt that one.",
                "{attacker} is finding a home for that {strike_type}!",
                "Beautiful {strike_type} from {attacker}, {defender} has no answer right now!",
                "{attacker} with a hard {strike_type}! That had some heat behind it!",
                "{attacker} slips the counter and cracks {defender} with a {strike_type}!",
                "{defender} is on skates after that {strike_type} from {attacker}!",
                "{attacker} feints and rips a {strike_type} to the {target}! Clean connection!",
                "THAT WAS CLEAN! {attacker} with a picture-perfect {strike_type}!",
                "{attacker} is unloading! Another {strike_type} gets through {defender}'s guard!",
                "{defender} shells up but {attacker} finds a gap with that {strike_type}!",
            ],
            "clinch": [
                "{attacker} lands a knee to {defender}'s {target} from the clinch!",
                "{attacker} fires off an elbow that opens a cut on {defender}!",
                "{defender} breaks the clinch with a stiff {strike_type}.",
                "{attacker} digs a knee into {defender}'s midsection!",
                "Dirty boxing from {attacker}, landing short punches in close!",
                "{attacker} with a brutal elbow from the clinch! {defender} is bloody!",
                "Knees in bunches from {attacker}! {defender} is wilting against the cage!",
                "{attacker} uses the clinch to land a devastating {strike_type}!",
                "{attacker} is relentless in the clinch, walking {defender} down with strikes!",
                "Crushing {strike_type} from {attacker} in the phone booth! {defender} is hurt!",
                "{attacker} out-muscles {defender} in the clinch and lands a nasty {strike_type}!",
            ],
            "ground": [
                "{attacker} lands a hammerfist on {defender}'s {target} from top position!",
                "{attacker} drops elbows on {defender} from mount!",
                "{defender} covers up well against the ground and pound.",
                "{attacker} postures up and rains down shots! {defender} is in trouble!",
                "{attacker} is methodical from the top, landing shot after shot.",
                "Heavy ground strikes from {attacker}! {defender} is just covering up!",
                "{attacker} with a crushing elbow from side control!",
                "{defender} is doing a good job limiting damage from the bottom.",
                "{attacker} is mauling {defender} on the ground! Those shots are heavy!",
                "{attacker} slices through the guard with a {strike_type}!",
                "{defender}'s face is getting marked up from the ground and pound!",
                "{attacker} transitions and lands a {strike_type} from a new angle!",
            ]
        }

        self.takedown_templates = {
            "success": [
                "{attacker} shoots for a takedown and gets it, taking {defender} down!",
                "{attacker} secures a double leg and slams {defender} to the mat!",
                "{defender} stuffs the first attempt but {attacker} chains to a single leg and finishes!",
                "Big takedown from {attacker}! {defender} needs to get back up!",
                "{attacker} drives through {defender} and puts them on the canvas!",
                "{attacker} times the takedown perfectly and gets the fight to the ground!",
                "A beautiful level change from {attacker} and {defender} is on their back!",
                "{attacker} uses {defender}'s momentum against them and scores the takedown!",
                "Slam dunk takedown! {attacker} lifts {defender} and deposits them on the mat!",
                "Trip takedown from {attacker}! {defender} is off balance and goes down!",
            ],
            "fail": [
                "{defender} stuffs the takedown attempt from {attacker}!",
                "{attacker} shoots but {defender} sprawls perfectly to defend!",
                "{attacker} can't get the takedown, {defender} defends well.",
                "{attacker} is stuffed against the cage by {defender}'s superior wrestling!",
                "{defender} shrugs off the takedown attempt like it was nothing!",
                "{attacker} shoots from too far out and {defender} easily stuffs it.",
                "{defender} reads the shot and stuffs it with a beautiful sprawl!",
                "{attacker} shoots but {defender} counters with a whizzer and stays on the feet!",
            ]
        }

        self.clinch_templates = {
            "enter": [
                "{fighter} secures the clinch against the cage!",
                "{fighter} ties up {opponent} in the center of the octagon.",
                "{fighter} closes the distance and gets both hands on {opponent}!",
                "{fighter} bullies {opponent} into the clinch!",
                "A brutal clinch entry from {fighter}! They've got {opponent} trapped!",
            ],
            "break": [
                "{fighter} breaks the clinch with a nice elbow!",
                "{fighter} pushes off and separates from the clinch.",
                "{fighter} uses a whizzer to break free and create distance!",
                "{fighter} explodes out of the clinch and resets in the center!",
            ]
        }

        self.ground_templates = {
            "sweep": [
                "{bottom} sweeps {top} and takes top position!",
                "{bottom} uses a beautiful butterfly sweep to reverse position!",
                "{bottom} throws up a leg and reverses {top}! Great scramble!",
                "Fantastic reversal by {bottom}! Now they're on top!",
            ],
            "submission_attempt": [
                "{attacker} locks in a tight {submission}!",
                "{attacker} hunts for a {submission} and has it locked in!",
                "{attacker} jumps on a {submission} attempt! This is deep!",
                "{attacker} is working for a {submission}, cranking on it!",
                "{attacker} sinks in the {submission}! Is this it?!",
            ],
            "submission_defend": [
                "{defender} defends the {submission} well, escaping the position!",
                "{defender} refuses to tap, fighting the {submission}!",
                "{defender} stays calm and works their way out of the {submission}!",
                "{defender} pops their head out and escapes the {submission} attempt!",
            ],
            "submission_tap": [
                "IT'S OVER! {defender} is forced to tap to the {submission}!",
                "{defender} taps! {attacker} gets the submission win via {submission}!",
                "That {submission} is deep! {defender} has no choice but to tap!",
                "{defender} is writhing in pain but refuses to tap! The ref steps in!",
            ],
            "stand_up": [
                "{fighter} scrambles back to standing!",
                "{fighter} gets up from bottom position, fight is back on the feet!",
                "{fighter} uses the cage to work back to their feet!",
                "Great reversal! {fighter} explodes up and we're back on the feet!",
            ]
        }

        self.knockdown_templates = [
            "{fighter} is dropped by a huge shot!",
            "{fighter} stumbles back, clearly rocked!",
            "{fighter} hits the canvas hard, the referee is checking on them!",
            "A massive shot drops {fighter}! They are in serious trouble!",
            "{fighter} is wobbled and goes down! The crowd is on their feet!",
        ]

        self.knockout_templates = [
            "IT'S ALL OVER! {fighter} is out cold! What a knockout!",
            "{fighter} crumples to the canvas! That was devastating!",
            "THE FIGHT IS STOPPED! {fighter} with a vicious knockout!",
            "{fighter} is unconscious before they hit the ground! Goodnight!",
        ]

        self.recovery_templates = [
            "{fighter} is on wobbly legs but the referee lets it continue!",
            "{fighter} survives the round! What a recovery!",
            "{fighter} is badly hurt but showing incredible heart to survive!",
        ]

        self.round_templates = {
            "start": [
                "Round {round_num} starts, {fighter1} and {fighter2} touch gloves!",
                "Round {round_num} is underway, {fighter1} takes the center immediately.",
                "Here we go with round {round_num}! Both fighters meet in the center!",
                "The referee waves them in for round {round_num}! Let's go!",
                "Round {round_num} begins! {fighter1} comes forward, {fighter2} circles!",
                "Here comes round {round_num}! Both fighters look ready to go to war!",
            ],
            "end": [
                "The round ends, {description}.",
                "Round {round_num} is over, {description}.",
                "That's the end of round {round_num}! {description}",
                "The horn sounds! {round_num} rounds in the books! {description}",
            ],
            "summary": [
                "Close round, neither fighter able to establish dominance.",
                "{fighter1} out-landed {fighter2} in that round with cleaner shots.",
                "{fighter2} did their best work in the clinch and on the ground.",
                "{fighter1} controlled the range and paced the round well.",
                "{fighter2} landed the heavier shots and did more damage.",
                "That was all {fighter1} — volume and pressure won the round.",
                "{fighter2} had their moments but couldn't sustain the output.",
                "A dominant round for {fighter1}, landing at will and stuffing takedowns.",
                "{fighter2} swarmed at the end but it might be too little, too late.",
            ]
        }

        self.pre_fight_templates = [
            "Welcome to tonight's main event! {fighter1} ({rec1}) vs {fighter2} ({rec2})!",
            "We're ready for the fight of the night! {fighter1} ({rec1}) takes on {fighter2} ({rec2})!",
            "Ladies and gentlemen, this is the moment we've been waiting for! {fighter1} ({rec1}) vs {fighter2} ({rec2})!",
            "The atmosphere is electric as {fighter1} ({rec1}) and {fighter2} ({rec2}) prepare to go to war!",
        ]

        self.walkout_templates = [
            "{fighter} makes their way to the cage, {description}.",
            "Here comes {fighter}, {description}. The crowd's reaction is electric!",
            "{fighter} is walking to the octagon now, {description}.",
            "The crowd roars as {fighter} enters the arena, {description}.",
            "{fighter} strides confidently to the cage, {description}.",
        ]

        self.between_round_templates = [
            "{fighter}'s corner is in their ear: '{advice}'",
            "The corner tells {fighter} they need to make adjustments. '{advice}'",
            "{fighter} gets instructions from the corner: '{advice}'",
            "Between rounds, {fighter}'s team works on them. '{advice}'",
            "The coaches are giving {fighter} specific instructions: '{advice}'",
            "{fighter} is being told to stay composed: '{advice}'",
            "The stool talk with {fighter}: '{advice}'",
        ]

        self.cut_commentary = [
            "There's blood pouring from a cut above {fighter}'s eye!",
            "The doctor is going to want to check that cut on {fighter}!",
            "{fighter} is leaking blood from a nasty gash!",
            "The cut on {fighter} is getting worse, that could be a problem!",
            "{fighter}'s face is a crimson mask! That cut is pouring blood!",
            "The blood is streaming down {fighter}'s face, making it hard to see!",
            "{fighter} wipes the blood away but it keeps coming!",
            "A deep gash has opened up on {fighter}! The ref might take a look!",
        ]

        self.swelling_commentary = [
            "{fighter}'s eye is swelling shut! That's going to affect their vision!",
            "The damage is showing on {fighter}'s face, that eye is closing up!",
            "Significant swelling around {fighter}'s eye!",
            "{fighter}'s orbital area is ballooning up from the accumulated damage!",
            "The swelling around {fighter}'s eye is getting worse each round!",
            "{fighter} blinks repeatedly, trying to clear the swelling from their vision!",
        ]

        self.leg_damage_commentary = [
            "{fighter}'s lead leg is chewed up from those kicks!",
            "{fighter} is limping slightly, those leg kicks are taking effect!",
            "The leg of {fighter} is bruised and marked up from the constant kicks!",
            "{fighter} is putting less weight on that lead leg now! Those kicks are paying off!",
            "The leg kicks are adding up! {fighter}'s mobility is compromised!",
            "{fighter} checks a kick but their leg is already too damaged to fully block it!",
        ]

        self.post_fight_templates = {
            "decision": [
                "After three hard rounds, the judges score the bout... {score_detail}",
                "We go to the scorecards! {score_detail}",
                "The judges have seen enough and it goes to the scorecards: {score_detail}",
                "This one goes to the judges! {score_detail}",
                "The scorecards are in! {score_detail}",
            ],
            "ko": [
                "WHAT A FINISH! {winner} wins by {method} in round {round}!",
                "That's all she wrote! {winner} with a {method} in round {round}!",
                "{winner} gets the {method} victory! An incredible performance!",
                "DEVASTATING! {winner} puts {loser} away with a {method} in round {round}!",
                "LIGHTS OUT! {winner} with a {method} for the ages in round {round}!",
            ],
            "submission": [
                "{winner} gets the tap! Submission victory via {method} in round {round}!",
                "Incredible grappling from {winner}! {method} in round {round}!",
                "{winner} forces the tap! That's a {method} victory!",
                "{winner} sinks it in and {loser} has no choice! {method} in round {round}!",
                "WHAT A SUBMISSION! {winner} with the {method}! {loser} had to tap!",
            ],
        }

        self.range_templates = {
            "close": [
                "{fighter} steps in, closing the distance on {opponent}!",
                "{fighter} cuts off the cage, moving into punching range!",
                "{fighter} pressures forward, now in the pocket!",
                "{fighter} slides in with a feint and closes the range!",
                "{fighter} stalks {opponent} down and enters striking range!",
                "{fighter} uses head movement to close the distance safely!",
            ],
            "retreat": [
                "{fighter} circles out, creating distance to reset!",
                "{fighter} steps back, returning to kicking range!",
                "{fighter} uses footwork to escape the pocket!",
                "{fighter} pivots off and backs to the center of the cage!",
                "{fighter} retreats to range, forcing {opponent} to pursue!",
            ],
        }

        self.ground_transition_templates = {
            "pass_guard": [
                "{fighter} bursts through {opponent}'s guard into side control!",
                "{fighter} slides past the legs, now in side control!",
                "{fighter} uses a beautiful pass to get past {opponent}'s guard!",
                "{fighter} smothers {opponent}'s guard and secures side control!",
                "{fighter} stacks {opponent} and passes to side control!",
            ],
            "mount": [
                "{fighter} swings a leg over and takes mount! Devastating position!",
                "{fighter} advances from side control to full mount!",
                "{fighter} catches {opponent} trying to escape and slides into mount!",
                "{fighter} is now mounted! {opponent} is in serious trouble!",
            ],
            "back_take": [
                "{fighter} sinks in both hooks and takes the back!",
                "{fighter} spins behind {opponent} as they scramble and secures back control!",
                "{fighter} jumps on the back! Both hooks are in!",
                "{fighter} transitions to the back, what a beautiful scramble!",
                "{fighter} takes the back! {opponent} is trapped against the cage!",
            ],
            "sweep": [
                "{bottom} sweeps {top} with a brilliant hip bump! Now on top!",
                "{bottom} uses a butterfly sweep to reverse position!",
                "{bottom} throws up a leg and reverses {top}! Great scramble!",
                "{bottom} catches {top} off balance and reverses into top position!",
                "{bottom} powers through and sweeps! Now they're on top!",
            ],
            "stand_up": [
                "{fighter} uses the cage to work back to their feet!",
                "{fighter} scrambles up, back to a standing battle!",
                "{fighter} posts up and explodes back to standing!",
                "{fighter} fights gravity and gets back up!",
                "{fighter} creates space and stands back up!",
            ],
            "takedown_into_guard": [
                "{attacker} lands the takedown into {defender}'s guard!",
                "{attacker} drives {defender} down and settles in the guard!",
                "{attacker} slams {defender} down, landing in half guard!",
                "Beautiful takedown! {attacker} is in {defender}'s guard!",
                "{attacker} chains the takedown and lands in a dominant position in guard!",
            ],
        }

        self.bonus_templates = [
            "Fight of the Night: {fotn} — both warriors earn {amount}!",
            "Performance of the Night: {potn} takes home an extra {amount}!",
            "Submission of the Night: {potn} with a beautiful finish, earning {amount}!",
            "Knockout of the Night: {potn} with the highlight reel finish, earning {amount}!",
        ]

    def _get_record(self, fighter: Fighter) -> str:
        return f"{fighter.wins}-{fighter.losses}-{fighter.draws}"

    def _get_streak_text(self, fighter: Fighter) -> str:
        if fighter.win_streak >= 3:
            return f"riding a {fighter.win_streak}-fight win streak"
        elif fighter.win_streak == 2:
            return f"won their last two"
        elif fighter.win_streak == 1:
            return f"coming off a win"
        elif fighter.loss_streak >= 3:
            return f"on a {fighter.loss_streak}-fight skid"
        elif fighter.loss_streak >= 1:
            return f"looking to bounce back from a loss"
        return "looking to make a statement"

    def _get_background_entrance(self, fighter: Fighter) -> Optional[str]:
        bg = fighter.background or "mma"
        templates = BACKGROUND_ENTRANCES.get(bg, BACKGROUND_ENTRANCES.get("mma", []))
        if templates:
            return random.choice(templates)
        return None

    def _get_personality_reaction(self, fighter: Fighter, opponent: Fighter, won: bool) -> Optional[str]:
        pid = fighter.personality_id or "humble"
        if won:
            templates = PERSONALITY_REACTIONS_WIN.get(pid, PERSONALITY_REACTIONS_WIN.get("humble", []))
        else:
            templates = PERSONALITY_REACTIONS_LOSS.get(pid, PERSONALITY_REACTIONS_LOSS.get("default", []))
        if templates:
            return random.choice(templates).format(fighter=fighter.name, opponent=opponent.name)
        return None

    def generate_pre_fight_buildup(self, fighter1: Fighter, fighter2: Fighter, context: Optional[Dict] = None) -> List[str]:
        parts = []

        template = random.choice(self.pre_fight_templates)
        parts.append(template.format(fighter1=fighter1.name, fighter2=fighter2.name,
                                     rec1=self._get_record(fighter1), rec2=self._get_record(fighter2)))

        if context:
            if context.get("show_streaks", True):
                streak1 = self._get_streak_text(fighter1)
                streak2 = self._get_streak_text(fighter2)
                st = random.choice(PREFIGHT_STREAK_TEMPLATES)
                parts.append(st.format(f1=fighter1.name, f2=fighter2.name, streak1=streak1, streak2=streak2))

            rivalry = context.get("rivalry_info")
            if rivalry and rivalry.get("has_history"):
                detail = rivalry.get("detail", "")
                rt = random.choice(PREFIGHT_RIVALRY_TEMPLATES)
                parts.append(rt.format(detail=detail))

            if context.get("show_matchup", True):
                rank1 = fighter1.rank if fighter1.rank != 1000 else 999
                rank2 = fighter2.rank if fighter2.rank != 1000 else 999
                lower_ranked = fighter1 if rank1 > rank2 else fighter2
                higher_ranked = fighter2 if rank1 > rank2 else fighter1
                diff = abs(rank1 - rank2)

                if diff > 5 and lower_ranked:
                    difficulty = "tough ask" if diff > 20 else ("step up" if diff > 10 else "interesting test")
                    mt = random.choice(PREFIGHT_MATCHUP_TEMPLATES)
                    parts.append(mt.format(
                        difficulty=difficulty,
                        lower_ranked_fighter=lower_ranked.name,
                        f1=fighter1.name, f2=fighter2.name,
                        style1=fighter1.background or "MMA", style2=fighter2.background or "MMA",
                        rank_info=f"#{higher_ranked.rank}-ranked {higher_ranked.name} faces #{lower_ranked.rank} {lower_ranked.name}" if diff > 10 else f"close rankings here",
                        goal1=self._get_style_goal(fighter1),
                        goal2=self._get_style_goal(fighter2),
                    ))

        return parts

    def _get_style_goal(self, fighter: Fighter) -> str:
        bg = fighter.background or "mma"
        bg_map = {
            "wrestling": "wrestle and control", "bjj": "take it to the ground and submit",
            "muay_thai": "clinch and unleash elbows and knees", "boxing": "box and move, land the cleaner shots",
            "judo": "get the clinch and throw", "taekwondo": "kick from distance with speed",
            "karate": "counter-strike with precision", "sambo": "mix takedowns with submissions",
            "kickboxing": "stand and trade, volume punching", "capoeira": "create chaos with unorthodox movement",
        }
        return bg_map.get(bg, "keep it standing and strike")

    def generate_strike_commentary(self, attacker: Fighter, defender: Fighter, strike_type: str, target: str, position: Position) -> str:
        pos_key = "ground" if "ground" in position.name.lower() else position.name.lower()
        if pos_key not in self.strike_templates:
            pos_key = "standing"
        template = random.choice(self.strike_templates[pos_key])
        return template.format(attacker=attacker.name, defender=defender.name, strike_type=strike_type, target=target)

    def generate_takedown_commentary(self, attacker: Fighter, defender: Fighter, success: bool) -> str:
        key = "success" if success else "fail"
        template = random.choice(self.takedown_templates[key])
        return template.format(attacker=attacker.name, defender=defender.name)

    def generate_clinch_commentary(self, fighter: Fighter, opponent: Fighter, action: str) -> str:
        key = "enter" if action == "enter" else "break"
        template = random.choice(self.clinch_templates[key])
        return template.format(fighter=fighter.name, opponent=opponent.name)

    def generate_ground_commentary(self, action: str, **kwargs) -> str:
        template = random.choice(self.ground_templates[action])
        return template.format(**kwargs)

    def generate_knockdown_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.knockdown_templates)
        return template.format(fighter=fighter.name)

    def generate_knockout_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.knockout_templates)
        return template.format(fighter=fighter.name)

    def generate_recovery_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.recovery_templates)
        return template.format(fighter=fighter.name)

    def generate_round_summary(self, fighter1: Fighter, fighter2: Fighter) -> str:
        template = random.choice(self.round_templates.get("summary", [""]))
        if not template:
            return ""
        return template.format(fighter1=fighter1.name, fighter2=fighter2.name)

    def generate_round_start(self, round_num: int, fighter1: Fighter, fighter2: Fighter) -> str:
        template = random.choice(self.round_templates["start"])
        return template.format(round_num=round_num, fighter1=fighter1.name, fighter2=fighter2.name)

    def generate_round_end(self, round_num: int, fighter1: Fighter, fighter2: Fighter, description: str = "close round") -> str:
        template = random.choice(self.round_templates["end"])
        return template.format(round_num=round_num, description=description)

    def generate_pre_fight(self, fighter1: Fighter, fighter2: Fighter) -> str:
        return self.generate_pre_fight_buildup(fighter1, fighter2, {
            "show_streaks": True, "show_matchup": True, "rivalry_info": None,
        })[0]

    def generate_walkout(self, fighter: Fighter, is_main_event: bool = False) -> str:
        entrance = self._get_background_entrance(fighter)
        if entrance:
            desc = entrance.format(fighter=fighter.name)
            if is_main_event:
                desc += " Headlining tonight's card!"
            template = random.choice(self.walkout_templates)
            return template.format(fighter=fighter.name, description=desc)

        desc_parts = []
        streak = self._get_streak_text(fighter)
        desc_parts.append(f"{streak}")
        if fighter.win_streak >= 3:
            desc_parts.append(f"and looking confident")
        if is_main_event:
            desc_parts.append(f"headlining tonight's card")

        description = ", ".join(desc_parts)
        template = random.choice(self.walkout_templates)
        return template.format(fighter=fighter.name, description=description)

    def generate_between_round(self, fighter: Fighter, round_num: int, needs_finish: bool, score_detail: str = "") -> str:
        advice_pool = []
        if needs_finish:
            advice_pool = [
                f"You need a finish! Go get it!",
                f"This is it! Leave it all in the cage!",
                f"Go for broke! You're down on the cards!",
                f"You're behind! Hunt for the finish — takedown, knockout, anything!",
                f"Desperate times! Empty the gas tank, this round is everything!",
                f"Champions find a way! Go out there and take it!",
            ]
        else:
            advice_pool = [
                f"Keep working, you're doing great!",
                f"Stick to the game plan!",
                f"Calm down, breathe, and execute.",
                f"Press forward, you're winning these exchanges!",
                f"Watch for his power shot, stay focused!",
                f"He's slowing down, pick up the pace!",
                f"Let your hands go, you're the better fighter!",
                f"Stay behind the jab, establish your range!",
                f"Mix in the takedown to keep him guessing!",
                f"Body work! Break him down to the body!",
                f"Patience, it's your round. Pick your shots!",
                f"He's loading up, make him miss and counter!",
                f"Pressure him! Don't let him breathe for a second!",
                f"Feint and find the opening, he's starting to read you.",
            ]

        advice = random.choice(advice_pool)
        template = random.choice(self.between_round_templates)
        result = template.format(fighter=fighter.name, advice=advice)
        if score_detail:
            result += f"\nScore update: {score_detail}"
        return result

    def generate_cut_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.cut_commentary)
        return template.format(fighter=fighter.name)

    def generate_swelling_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.swelling_commentary)
        return template.format(fighter=fighter.name)

    def generate_leg_damage_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.leg_damage_commentary)
        return template.format(fighter=fighter.name)

    def generate_range_commentary(self, fighter: Fighter, opponent: Fighter, action: str) -> str:
        key = "close" if action == "close" else "retreat"
        template = random.choice(self.range_templates[key])
        return template.format(fighter=fighter.name, opponent=opponent.name)

    def generate_ground_transition_commentary(self, action: str, **kwargs) -> str:
        template = random.choice(self.ground_transition_templates[action])
        return template.format(**kwargs)

    def generate_post_fight(self, winner: Fighter, method: str, round_num: int = None, is_decision: bool = False, loser: Fighter = None) -> str:
        if not winner:
            return "The fight goes to the scorecards... It's a DRAW!"
        loser_name = loser.name if loser else "their opponent"
        if is_decision:
            template = random.choice(self.post_fight_templates["decision"])
            score_detail = f"{winner.name} gets the nod"
            return template.format(score_detail=score_detail)
        elif "KO" in method or "TKO" in method:
            template = random.choice(self.post_fight_templates["ko"])
            return template.format(winner=winner.name, loser=loser_name, method=method, round=round_num)
        else:
            template = random.choice(self.post_fight_templates["submission"])
            return template.format(winner=winner.name, loser=loser_name, method=method, round=round_num)

    def generate_post_fight_reaction(self, winner: Fighter, loser: Fighter) -> Optional[str]:
        return self._get_personality_reaction(winner, loser, won=True)

    def generate_post_fight_loss(self, loser: Fighter, winner: Fighter) -> Optional[str]:
        return self._get_personality_reaction(loser, winner, won=False)

    def generate_bonus_commentary(self, fight_of_night: Optional[str] = None, perf_of_night: Optional[str] = None,
                                  amount: str = "$50,000") -> str:
        results = []
        if fight_of_night:
            results.append(f"Fight of the Night: {fight_of_night} — both warriors earn {amount}!")
        if perf_of_night:
            results.append(f"Performance of the Night: {perf_of_night} takes home {amount}!")
        return "\n".join(results) if results else ""
