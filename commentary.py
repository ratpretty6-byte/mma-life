import random
from typing import Dict, List, Optional
from fighter import Fighter
from positions import PositionSystem, Position
from utils import SEVERITY_TIERS

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
        "{fighter} slaps their own head and locks eyes with their opponent, ready for war.",
    ],
    "judo": [
        "{fighter} steps onto the canvas with a measured, purposeful stride, gripping imaginary sleeves.",
        "{fighter} circles with a wide base, hands low, looking for that explosive hip toss.",
        "{fighter} adjusts their collar grip habitually, the judoka instincts surfacing.",
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
                "Precise {strike_type} from {attacker} — {defender} never saw that coming!",
                "{attacker} measures {defender} and lands a sharp {strike_type}!",
                "{attacker} is starting to time {defender}'s movement — there's that {strike_type}!",
                "{attacker} steps in with a {strike_type} that snaps {defender}'s head sideways!",
                "Beautiful shot by {attacker}! {defender} eating that {strike_type} with their face!",
                "{attacker} with laser focus — {strike_type} to the {target} is automatic!",
                "{defender} absorbs a heavy {strike_type} from {attacker} — that one had bad intentions!",
                "{attacker} is in a rhythm now, popping that {strike_type} at will!",
                "CRACK! {attacker} lands a {strike_type} flush on {defender}'s {target}!",
                "{attacker} is dealing damage every time they step forward with that {strike_type}!",
                "Sharp exchange ends with {attacker}'s {strike_type} getting through clean!",
                "{attacker} counters brilliantly — {strike_type} meets {defender} coming in!",
                # === NEW PLAY-BY-PLAY REALISM TEMPLATES ===
                "{attacker} snaps a crisp {strike_type} that catches {defender} on the chin!",
                "{attacker} shifts weight and rips a {strike_type} to {defender}'s {target} — clean connection!",
                "{attacker} feints the jab and comes over the top with a {strike_type}!",
                "{attacker} steps in with a {strike_type}, splitting {defender}'s guard!",
                "{attacker} measures distance and pops a {strike_type} that snaps {defender}'s head back!",
                "{attacker} doubles up on the {strike_type}, landing the second one flush!",
                "{attacker} sells the takedown and unloads a {strike_type} as {defender} drops their hands!",
                "{attacker} switches stance mid-combo and cracks {defender} with a {strike_type}!",
                "{attacker} is timing {defender}'s movement now — another {strike_type} gets through!",
                "{attacker} steps to the outside angle and lands a {strike_type} to the {target}!",
                "{attacker} uses a subtle head fake before firing that {strike_type} straight down the pipe!",
                "{attacker} paws with the jab, pulls {defender}'s guard up, then goes {strike_type} to the {target}!",
                "{attacker} catches {defender} loading up, fires a {strike_type} that lands first!",
                "{attacker} lunges in with a {strike_type} — it crashes off {defender}'s {target}!",
                "{attacker} fires a {strike_type} in combination, finding the range more each time!",
                "{attacker} digs a {strike_type} to the {target} — that one will leave a mark!",
                "{attacker} throws a sharp {strike_type} that slices through {defender}'s defense!",
                "{attacker} cuts off the cage and plants a {strike_type} on {defender}'s {target}!",
                "{attacker} is crowding {defender} and firing short {strike_type}s to the {target}!",
                "{attacker} waits for {defender} to commit, then sidesteps and lands a {strike_type}!",
                "{attacker} flicks a {strike_type} that seems to come from nowhere — lands clean!",
                "{attacker} puts more hip into that {strike_type} — massive pop on impact!",
                "{attacker} feints high, goes low, comes back up with a {strike_type} to the {target}!",
                "{attacker} is a step ahead of {defender} — that {strike_type} lands with authority!",
                "{attacker} targets the {target} with a {strike_type}, and it pays off big!",
                "{attacker} with a beautiful level change in the {strike_type} — {defender} was late on that!",
                "{attacker} times {defender}'s rhythm and cracks them with a {strike_type}!",
                "{attacker} slides to the inside and fires a {strike_type} off the back foot!",
                "{attacker} stays patient, picks the moment, and lands a {strike_type} to the {target}!",
                "{attacker} uses the jab as a rangefinder, then lands a {strike_type} to the {target}!",
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
                "Devastating knee from {attacker} in the clinch — {defender} is buckling!",
                "{attacker} is punishing {defender} against the cage with short elbows!",
                "Clinch war! {attacker} gets the better of the exchange with a brutal {strike_type}!",
                "{attacker} muscles {defender} into the fence and goes to work with knees!",
                "Dirty boxing clinic from {attacker} — {defender} can't get free!",
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
                "Ground and pound from hell! {attacker} is relentless from top position!",
                "{attacker} postures and drops bombs — {defender} is covering up desperately!",
                "Brutal elbow from {attacker} opens a gash on {defender}!",
                "{attacker} is smothering {defender} from the top — landing at will!",
                "{attacker} in mount — this is a terrible place for {defender}!",
                "SHORT strikes from {attacker} on the ground — {defender} needs to escape!",
            ],
            "critical": [
                "CRITICAL HIT! {attacker} lands a devastating {strike_type} flush on {defender}'s {target}!",
                "HUGE shot from {attacker}! That {strike_type} landed perfectly on {defender}'s {target}!",
                "{defender} got absolutely RIPPED by that {strike_type} to the {target}!",
                "That {strike_type} from {attacker} had EVERYTHING behind it — {defender} is in trouble!",
                "WHAT A SHOT! {attacker} lands a perfect {strike_type} that wobbles {defender}!",
            ],
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
                "{bottom} powers through and sweeps! Now they're on top!",
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
                "{defender} stays calm and works their way out of the {submission} attempt!",
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

        self.tko_templates = [
            "{winner} swarms with ground strikes and the referee has seen enough! TKO!",
            "The referee dives in to save {loser}! {winner} wins by TKO!",
            "{winner} follows {loser} to the ground and unloads — the ref steps in! TKO!",
            "Ground and pound finishes it! The referee waves it off!",
            "{winner} pours on the punishment and the fight is stopped! TKO!",
            "{loser} can't defend themselves on the ground — referee stoppage!",
            "A furious barrage from {winner} forces the referee to intervene!",
        ]

        self.recovery_templates = [
            "{fighter} is on wobbly legs but the referee lets it continue!",
            "{fighter} survives the round! What a recovery!",
            "{fighter} is badly hurt but showing incredible heart to survive!",
            "{fighter} gathers themselves — incredible toughness!",
        ]

        self.stopped_templates = [
            "The referee jumps in — it's all over!",
            "Waved off! The referee stops the fight!",
            "TKO! The referee has seen enough!",
        ]

        self.round_templates = {
            "start": [
                "Round {round_num} starts, {fighter1} and {fighter2} touch gloves!",
                "Round {round_num} is underway, {fighter1} takes the center immediately.",
                "Here we go with round {round_num}! Both fighters meet in the center!",
                "The referee signals round {round_num} — let's go!",
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
            "A deep gash has opened up on {fighter}!",
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

        self.body_shot_commentary = [
            "That body shot lands clean! {defender} gasps for air!",
            "A vicious body shot from {attacker}! {defender} is feeling that!",
            "{attacker} works the body, breaking {defender} down piece by piece!",
            "The body work from {attacker} is paying off — {defender} is slowing down!",
            "Another body shot from {attacker}! You can see {defender} wilting!",
        ]

        self.liver_shot_commentary = [
            "RIGHT TO THE LIVER! That shot folds {defender}!",
            "Liver shot! {attacker} digs deep and {defender} is in agony!",
            "A brutal body shot to the liver — {defender} is hurting badly!",
            "Devastating liver kick! {defender} is crumpling!",
            "{attacker} finds the liver with a perfect shot! {defender} is gasping!",
        ]

        self.solar_plexus_commentary = [
            "BODY SHOT! {attacker} drives a shot into the solar plexus — {defender} is winded!",
            "That shot to the midsection takes {defender}'s breath away!",
            "{attacker} lands flush on the solar plexus — {defender} is struggling to breathe!",
            "A perfect shot to the solar plexus from {attacker}. {defender} is hurt!",
        ]

        self.rib_shot_commentary = [
            "{attacker} lands a hard shot to {defender}'s ribs — those are starting to add up!",
            "A vicious shot to the ribs from {attacker}! {defender} winces!",
            "{attacker} targets the ribs — you can see that shot landed deep!",
            "{defender} may have cracked ribs from that {strike_type}!",
        ]

        self.breathing_commentary = [
            "{fighter} is breathing heavily now, that body work is paying off!",
            "{fighter} is gasping for air — body damage is taking its toll!",
            "{fighter} is laboring to breathe, hands dropping below the chin!",
            "{fighter} looks exhausted, the body shots have slowed them significantly!",
            "{fighter} can't seem to catch their breath!",
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
            "tko_referee": [
                "The referee steps in and stops the fight! {winner} by TKO!",
                "Referee stoppage! {winner} dominated {loser} into oblivion!",
                "The ref has seen enough — {winner} wins by TKO in round {round}!",
            ],
            "tko_ground": [
                "Ground and pound finishes it! {winner} by TKO in round {round}!",
                "{winner} unleashes on the ground and the ref jumps in!",
                "The punishment on the ground was too much — TKO for {winner}!",
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
                "{fighter} is marching forward, cutting off the cage!",
                "{fighter} pressures {opponent} against the fence!",
            ],
            "retreat": [
                "{fighter} circles out, creating distance to reset!",
                "{fighter} steps back, returning to kicking range!",
                "{fighter} uses footwork to escape the pocket!",
                "{fighter} pivots off and backs to the center of the cage!",
                "{fighter} retreats to range, forcing {opponent} to pursue!",
                "{fighter} uses lateral movement to circle away from danger!",
                "{fighter} backpedals and resets in the center!",
            ],
        }

        self.pacing_templates = [
            "{fighter} is pressing forward, looking to land the bigger shot!",
            "{fighter} is content to fight from range, making {opponent} lead!",
            "{fighter} paws with the jab, measuring the distance!",
            "{fighter} is circling, looking for an opening!",
            "Both fighters are exchanging feints, neither wanting to commit!",
            "{fighter} is controlling the center of the cage!",
            "The pace slows as both fighters reset and re-measure!",
            "{fighter} faints high, dips low, trying to draw a reaction!",
            "{opponent} is being walked down by {fighter}!",
            "{fighter} takes a half-step back, drawing {opponent} into the pocket!",
            "{fighter} pumps the jab, keeping {opponent} at bay!",
            "{opponent} can't find the range — {fighter}'s footwork is on point!",
            "There's a pause as both fighters regroup in the center!",
            "Neither fighter wants to overcommit here — patience is key!",
            "{fighter} is using head movement to draw a miss and counter!",
            "The crowd murmurs as the fighters circle, each waiting for the right moment!",
            "{fighter} switches stances, trying to create a different look!",
            "A feeling-out process here, both fighters establishing their rhythm!",
            "{fighter} is finding a rhythm with that jab!",
            "Stalemate in the center — who will make the first move?",
        ]

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
                "{attacker} chains the takedown and lands in a dominant position!",
            ],
        }

        self.stamina_commentary = [
            "{fighter} is showing signs of fatigue — heavy breathing!",
            "{fighter}'s pace is slowing down considerably!",
            "Both fighters are gassed but {fighter} is feeling it more!",
            "{fighter} is carrying a lot of ring rust — labored!",
            "{fighter}'s legs are heavy — can barely move!",
        ]

        self.desperation_commentary = [
            "{fighter} is winging wild shots looking for a finish!",
            "Desperation from {fighter} — throwing everything forward!",
            "{fighter} knows time is running out — pressing hard!",
            "Last chance energy from {fighter}!",
            "{fighter} turns it on — this is survival mode!",
        ]

        self.comeback_commentary = [
            "{fighter} is turning this fight around!",
            "What a response from {fighter}! Back in this fight!",
            "{fighter} digs deep and starts landing again!",
            "The tide is turning! {fighter} is finding a second wind!",
        ]

        self.momentum_commentary = [
            "{fighter} is on fire right now! Momentum is all theirs!",
            "{fighter} is building serious momentum — {opponent} can't get anything going!",
            "{fighter} is in the zone! Every shot is landing!",
            "The crowd is feeding off {fighter}'s energy! What a surge!",
            "{fighter} is raining down shots — {opponent} needs to weather this storm!",
            "{opponent} is wilting under {fighter}'s pressure!",
        ]

        self.crowd_commentary = [
            "The crowd is on their feet! This is incredible!",
            "The atmosphere is electric in here tonight!",
            "The fans are roaring — they love what they're seeing!",
            "What an atmosphere! This is why we love this sport!",
            "The roof is coming off! What a fight we have here!",
            "You can feel the energy in the building!",
            "The crowd is going WILD! What a moment!",
            # === NEW EXPANDED CROWD REACTIONS ===
            "The crowd gasps as that shot lands clean!",
            "The arena erupts — what a sequence!",
            "A collective 'OHHH' from the crowd — that one hurt!",
            "You can hear the thud from the cheap seats!",
            "The fans are on their feet, sensing a finish!",
            "The building is rocking! These two are putting on a show!",
            "A hush falls over the crowd as {defender} is in trouble!",
            "The crowd noise is deafening! What an atmosphere!",
            "Pandemonium in the crowd — what a moment!",
        ]

        self.defensive_narrative_templates = [
            "{defender} slips the {strike_type} and fires back with a left hook!",
            "{defender} parries the {strike_type} and creates an angle to escape!",
            "{defender} checks the kick and counters with a straight right!",
            "{defender} rolls under the {strike_type} and comes up firing!",
            "{defender} shells up, absorbing the {strike_type} on the forearms!",
            "{defender} uses head movement to make the {strike_type} miss by inches!",
            "{defender} catches the {strike_type} on the elbow — smart defense!",
            "{defender} leans back, letting the {strike_type} sail past!",
            "{defender} smothers the {strike_type} by stepping inside and clinching!",
            "{defender} blocks the {strike_type} high and answers with a body shot!",
            "{defender} ducks under the {strike_type} and resets to the outside!",
            "{defender} circles away, avoiding the {strike_type} entirely!",
            "{defender} catches the kick and counters with a {strike_type} of their own!",
            "{defender} parries twice in a row, timing {attacker}'s rhythm!",
        ]

        self.contextual_overlay_phrases = {
            "fatigue": [
                " but he's looking tired, losing snap on his punches",
                " but the body work is slowing him down noticeably",
                " but his hands are dropping as the fatigue sets in",
                " but his output is fading fast as the round wears on",
            ],
            "momentum": [
                " — the crowd is roaring, he's feeding off this energy!",
                " — he's building serious momentum and can't be stopped!",
                " — the confidence is growing with every exchange!",
                " — he's in a rhythm now, everything is landing!",
            ],
            "leg_damage": [
                " — he's barely putting weight on that lead leg now",
                " — his compromised stance is making him a sitting duck",
                " — those leg kicks have completely changed his movement",
            ],
            "body_work": [
                " — the body work is paying off, his pace is dropping",
                " — he's starting to wilt from the accumulated body damage",
                " — you can see the body shots taking effect, slowing his hands",
                " — his breathing is labored from those body attacks",
            ],
        }

        self.exchange_templates = [
            "Both trade in the pocket! {a} lands {a_result} while {b} answers {b_result}!",
            "Exchange in the center! {a} fires {a_result} — but {b} counters {b_result}!",
            "Both throw at once! {a} scores {a_result} and {b} comes back {b_result}!",
            "Wild exchange! {a} digs {a_result}, {b} fires back {b_result}!",
            "They trade leather! {a} cracks {a_result} as {b} lands {b_result}!",
        ]

        self.progressive_finish_templates = [
            "{fighter} is hurt! On wobbly legs, {opponent} smells blood!",
            "{fighter} is wobbled! They don't know where they are right now!",
            "{fighter} is on the verge! One more shot could end this!",
            "{fighter} is out on their feet! The referee is watching closely!",
            "{fighter} is in survival mode, just trying to stay upright!",
            "{fighter} is fading fast — this could be the beginning of the end!",
        ]

        self.weight_cut_templates = [
            "{fighter} drained {lbs}lbs this week — the question is how much that took out of him.",
            "{fighter} looked gaunt at weigh-ins. Will the cardio hold up in the later rounds?",
            "There are concerns about {fighter}'s weight cut — he looked depleted on the scales.",
            "{fighter} rehydrated well, but tough weight cuts have a way of catching up to you.",
            "The weight cut was brutal for {fighter}. He's giving up size tonight.",
        ]

        self.round_arc_templates = [
            "An action-packed round! {f1} found the range early and started landing the cross. {f2} is slowing as the body shots accumulate.",
            "{f1} controlled the clinch and landed heavy knees. {f2} needs to keep this standing and establish the jab.",
            "All {f1} that round — volume, pressure, and that takedown defense was impenetrable. {f2} needs to make adjustments.",
            "Close round. {f1}'s leg kicks are adding up, limiting {f2}'s movement significantly. The leg damage could be the story of this fight.",
            "{f2} survived a late surge from {f1} and looked sharp on the counter. This fight is still very much in the balance.",
            "{f1} is pulling away. The speed and precision are making the difference. {f2} needs to find something special.",
            "{f2} came on strong in the final minute, staggering {f1} with a right hand. Momentum swing?",
            "A dominant round for {f1} — they're in complete control. {f2} is being outclassed so far.",
            "{f1} with a measured round, using the jab to set up power shots. {f2} can't find the range.",
            "Both fighters had their moments, but {f1}'s pressure and volume edged it. {f2} needs to let their hands go.",
        ]

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

    # ============================================================
    # TIME-AWARE COMMENTARY
    # ============================================================

    def _time_stamp(self, round_num: int, time_elapsed: int) -> str:
        """Generate timestamp string R# M:SS"""
        remaining = max(0, 300 - time_elapsed)
        mins = remaining // 60
        secs = remaining % 60
        return f"R{round_num} {mins}:{secs:02d}"

    def _urgency_phrase(self, round_num: int, time_elapsed: int, is_title: bool) -> str:
        """Generate urgency-based commentary phrases based on round time remaining."""
        remaining = 300 - time_elapsed
        if remaining <= 10:
            return random.choice([
                "The horn is about to sound!",
                "Final seconds of the round!",
                "Both fighters know time is almost up!",
                "This is the last ten seconds!",
            ])
        elif remaining <= 30:
            return random.choice([
                "Thirty seconds left in the round!",
                f"{self._time_stamp(round_num, time_elapsed)} — the pressure is mounting!",
                "The pace picks up as the round winds down!",
            ])
        return ""

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

                # Reach comparison
                reach_diff = fighter1.reach - fighter2.reach
                if abs(reach_diff) >= 3:
                    longer_fighter = fighter1 if reach_diff > 0 else fighter2
                    parts.append(f"{longer_fighter.name} has a {abs(reach_diff)}-inch reach advantage")

                # Weight comparison (if same weight class, mention natural weight)
                weight_diff = fighter1.base_weight_lbs - fighter2.base_weight_lbs
                if abs(weight_diff) >= 10:
                    heavier = fighter1 if weight_diff > 0 else fighter2
                    parts.append(f"{heavier.name} comes in {abs(weight_diff)}lbs heavier")

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
        pos_key = "ground" if Position.is_ground(position) else position.name.lower()
        if pos_key not in self.strike_templates or pos_key == "dstance":
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

    def generate_tko_commentary(self, winner: Fighter, loser: Fighter, method: str) -> str:
        template = random.choice(self.tko_templates)
        return template.format(winner=winner.name, loser=loser.name, method=method)

    def generate_recovery_commentary(self, fighter: Fighter) -> str:
        template = random.choice(self.recovery_templates)
        return template.format(fighter=fighter.name)

    def generate_stoppage_commentary(self, winner: Fighter, loser: Fighter, method: str, round_num: int) -> str:
        if "Referee" in method:
            template = random.choice(self.post_fight_templates["tko_referee"])
            return template.format(winner=winner.name, loser=loser.name, round=round_num)
        else:
            template = random.choice(self.post_fight_templates["tko_ground"])
            return template.format(winner=winner.name, loser=loser.name, round=round_num)

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

    def generate_body_shot_commentary(self, attacker: Fighter, defender: Fighter) -> str:
        template = random.choice(self.body_shot_commentary)
        return template.format(attacker=attacker.name, defender=defender.name)

    def generate_pacing_commentary(self, fighter: Fighter, opponent: Fighter, phase: str = "exchanges") -> Optional[str]:
        if random.random() < 0.5:
            return None
        template = random.choice(self.pacing_templates)
        return template.format(fighter=fighter.name, opponent=opponent.name)

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
        elif "TKO (Referee" in method:
            template = random.choice(self.post_fight_templates["tko_referee"])
            return template.format(winner=winner.name, loser=loser_name, round=round_num)
        elif "TKO (Ground" in method:
            template = random.choice(self.post_fight_templates["tko_ground"])
            return template.format(winner=winner.name, loser=loser_name, round=round_num)
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

    def generate_momentum_commentary(self, fighter: Fighter, opponent: Fighter, momentum: int) -> Optional[str]:
        if abs(momentum) < 20:
            return None
        template = random.choice(self.momentum_commentary)
        return template.format(fighter=fighter.name, opponent=opponent.name)

    def generate_crowd_commentary(self, excitement: int) -> Optional[str]:
        if excitement < 70:
            return None
        return random.choice(self.crowd_commentary)

    def generate_fatigue_commentary(self, fighter: Fighter, fatigue: float) -> Optional[str]:
        """Generate fatigue-related commentary based on fatigue level."""
        if fatigue < 0.4:
            return None
        weighted = [(t, 1.0 - abs(fatigue - t)) for t in [0.4, 0.55, 0.7, 0.85]]
        valid = [(t, w) for t, w in weighted if w > 0]
        if not valid:
            return None
        template = random.choice(self.stamina_commentary)
        return template.format(fighter=fighter.name)

    def generate_desperation_commentary(self, fighter: Fighter, is_losing: bool) -> Optional[str]:
        """Generate desperation commentary when fighter is losing badly."""
        if not is_losing:
            return None
        if random.random() < 0.3:
            return random.choice(self.desperation_commentary).format(fighter=fighter.name)
        return None

    def generate_comeback_commentary(self, fighter: Fighter, was_losing: bool, now_ahead: bool) -> Optional[str]:
        """Generate comeback commentary."""
        if was_losing and now_ahead:
            return random.choice(self.comeback_commentary).format(fighter=fighter.name)
        return None