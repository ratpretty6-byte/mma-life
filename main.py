import time
import sys
import random
from datetime import datetime, timedelta

from fighter import Fighter
from training import TrainingSystem, TrainingCamp
from promotion import Promotion, create_promotions
from career import CareerSystem
from finance import FinancialSystem
from health import HealthSystem
from media import MediaSystem
from events import EventSystem, Event
from fight import Fight
from strategy import StrategySystem, STRATEGIES
from generator import generate_fighter_pool
import utils

FIGHT_SPEED = 0.8

def character_creation():
    print("=" * 50)
    print("           MMA LIFE SIMULATOR")
    print("=" * 50)
    name = input("Enter fighter name: ").strip()
    if not name:
        first, last = utils.generate_name()
        name = f"{first} {last}"
        print(f"Using generated name: {name}")

    age = 0
    while age < 18 or age > 40:
        try:
            age = int(input("Enter age (18-40): "))
        except ValueError:
            pass

    weight_lbs = 0
    print("\nSelect weight class:")
    for i, wc in enumerate(utils.WEIGHT_CLASSES, 1):
        print(f"{i}. {wc['name']} ({wc['min']}-{wc['max']} lbs)")
    wc_choice = 0
    while wc_choice < 1 or wc_choice > len(utils.WEIGHT_CLASSES):
        try:
            wc_choice = int(input("Choice: "))
        except ValueError:
            pass
    chosen_wc = utils.WEIGHT_CLASSES[wc_choice - 1]
    weight_lbs = random.randint(chosen_wc["min"], chosen_wc["max"])

    print("\nSelect background:")
    backgrounds = ["mma", "wrestling", "bjj", "muay_thai", "boxing", "judo", "taekwondo", "karate", "sambo", "kickboxing", "capoeira"]
    for idx, bg in enumerate(backgrounds, 1):
        print(f"{idx}. {bg.title()}")
    bg_choice = 0
    while bg_choice < 1 or bg_choice > len(backgrounds):
        try:
            bg_choice = int(input("Choice: "))
        except ValueError:
            pass
    background = backgrounds[bg_choice - 1]

    return Fighter(name, age, weight_lbs, background)

def pick_strategy(allow_skip=True):
    print("\nSelect strategy:")
    for idx, s in enumerate(STRATEGIES, 1):
        print(f"{idx}. {s['name']:25s} - {s['description']}")
    if allow_skip:
        print(f"{len(STRATEGIES) + 1}. Keep current strategy")
    choice = 0
    while choice < 1 or choice > len(STRATEGIES) + (1 if allow_skip else 0):
        try:
            choice = int(input("Choice: "))
        except ValueError:
            pass
    if allow_skip and choice == len(STRATEGIES) + 1:
        return None
    return STRATEGIES[choice - 1]["id"]

def run_fight_night(fighter, opponent, career, training, finance, health, media, event_sys, event, fight_booking):
    global FIGHT_SPEED

    print("\n" + "=" * 50)
    print(f"FIGHT NIGHT: {fighter.name} vs {opponent.name}")
    print("=" * 50)

    print("\nSelect your strategy:")
    strat_id = pick_strategy(allow_skip=False)

    is_title = fight_booking.is_title_fight
    fight = Fight(fighter, opponent, rounds=3, is_title_fight=is_title)
    fight.strategy1.set_pre_fight_strategy(strat_id)

    ai_archetype = opponent.archetype
    ai_strat_map = {
        "brawler": "aggressive_striking", "counter_striker": "defensive_striking",
        "wrestler": "wrestling_focus", "submission_artist": "submission_hunting",
        "kickboxer": "kickboxing_focus", "boxer": "boxing_focus",
        "muay_thai": "muay_thai_focus", "clinch_fighter": "clinch_dominance",
        "balanced": random.choice([s["id"] for s in STRATEGIES]),
    }
    ai_strat = ai_strat_map.get(ai_archetype, "balanced")
    if ai_strat == "balanced":
        ai_strat = random.choice([s["id"] for s in STRATEGIES])
    fight.strategy2.set_pre_fight_strategy(ai_strat)

    for event_data in fight.simulate_fight_gen(FIGHT_SPEED):
        etype = event_data["type"]

        if etype == "action":
            print(f"  {event_data['text']}")
            time.sleep(FIGHT_SPEED)

        elif etype == "damage":
            print(f"  {event_data['text']}")
            time.sleep(FIGHT_SPEED * 0.6)

        elif etype == "knockout":
            print(f"\n*** {event_data['text']} ***")
            print(f"Winner: {event_data['winner']} via {event_data['method']} (Round {event_data['round']})")
            time.sleep(1)

        elif etype == "submission":
            print(f"\n*** {event_data['text']} ***")
            print(f"Winner: {event_data['winner']} via {event_data['method']} (Round {event_data['round']})")
            time.sleep(1)

        elif etype == "decision":
            print(f"\n*** {event_data['text']} ***")
            print(f"Winner: {event_data['winner']} via {event_data['method']}")
            if "details" in event_data:
                print(f"  {event_data['details']}")
            time.sleep(1)

        elif etype == "pre_fight":
            print(f"\n{event_data['text']}")
            time.sleep(1.5)

        elif etype == "walkout":
            print(f"\n{event_data['text']}")
            time.sleep(1.5)

        elif etype == "round_start":
            print(f"\n--- {event_data['text']} ---")
            time.sleep(1)

        elif etype == "round_end":
            print(f"\n{event_data['text']}")
            time.sleep(1)

        elif etype == "score_update":
            print(f"  Judges score this round: {event_data['score']}")

        elif etype == "between_round":
            print(f"\n{event_data['text']}")
            time.sleep(1.5)

        elif etype == "strategy_prompt":
            print(f"\n--- Between Round {event_data['round']} ---")
            print(f"Your stamina: {event_data['f1_stamina']:.0f}%")
            print(f"Opponent stamina: {event_data['f2_stamina']:.0f}%")
            if event_data.get("score_detail"):
                print(f"Score: {event_data['score_detail']}")
            new_strat = pick_strategy(allow_skip=True)
            if new_strat:
                fight.strategy1.adjust_strategy(new_strat)

        elif etype == "post_fight":
            print(f"\n{event_data['text']}")

        elif etype == "complete":
            result = event_data
            break

    print("\n" + "=" * 50)
    print("FIGHT OVER")
    print("=" * 50)
    return result

def main():
    global FIGHT_SPEED
    fighter = character_creation()

    print("\nGenerating fight world with 5000 fighters...")
    weight_classes = [wc["name"] for wc in utils.WEIGHT_CLASSES]
    promotions = create_promotions(weight_classes)
    world_promo, national_promo, regional_promo = promotions

    all_fighters = generate_fighter_pool(promotions, 5000)

    regional_promo.sign_fighter(fighter, 4)
    print(f"Signed with {regional_promo.name}!")

    career = CareerSystem(fighter)
    career.sign_with_promotion(regional_promo, 4)
    training = TrainingSystem(fighter)
    finance = FinancialSystem(fighter)
    health = HealthSystem(fighter)
    media = MediaSystem(fighter)
    event_sys = EventSystem()

    fighter.net_worth = 5000
    finance.net_worth = 5000

    current_event = None
    current_fight_booking = None
    game_over = False

    while not game_over:
        if fighter.retired:
            print(f"\n{fighter.name} has retired from MMA.")
            print(f"Final Record: {fighter.get_record_string()}")
            print(f"Career Earnings: {utils.format_currency(career.career_earnings)}")
            print(f"Peak Rank: #{fighter.peak_rank}")
            break

        record_str = fighter.get_record_string()
        rank_str = f"#{fighter.rank}" if career.current_promotion else "FA"
        promo_str = career.current_promotion.name if career.current_promotion else "Free Agent"
        champ_str = ""
        if career.current_promotion:
            champ = career.current_promotion.champions.get(fighter.weight_class)
            if champ == fighter:
                champ_str = " [CHAMPION]"

        print(f"\n{'=' * 50}")
        print(f"{fighter.name}{champ_str} | {record_str} | Rank: {rank_str} | {promo_str}")
        print(f"Net: {utils.format_currency(finance.net_worth)} | Age: {fighter.age}")
        print(f"{'=' * 50}")
        print("1. Training Camp")
        print("2. Book Fight")
        print("3. Fight Night!")
        print("4. Career Stats")
        print("5. Finances")
        print("6. Personal (Gym/Agent/Weight)")
        print("7. Advance Time")
        print("8. Exit / Retire")
        choice = input("Choice: ")

        if choice == "1":
            print(f"\n=== Training Camp ===")
            print(f"Current fatigue: {training.fatigue:.0%}")
            print("1. Start Camp")
            print("2. Train Day")
            print("3. End Camp")
            tc = input("Choice: ")

            if tc == "1":
                if training.current_camp:
                    print("Already in a camp! End it first.")
                    continue
                camps = TrainingCamp.get_available_camps()
                print("\nAvailable camps:")
                for idx, c in enumerate(camps, 1):
                    print(f"{idx}. {c.name} ({c.duration_weeks}w, {utils.format_currency(c.cost)})")
                camp_choice = 0
                while camp_choice < 1 or camp_choice > len(camps):
                    try:
                        camp_choice = int(input("Select camp: "))
                    except ValueError:
                        pass
                camp = camps[camp_choice - 1]

                if not finance.can_afford(camp.cost):
                    print(f"Cannot afford {utils.format_currency(camp.cost)} camp!")
                    continue

                print("\nAvailable drills:")
                for idx, d in enumerate(camp.available_drills, 1):
                    print(f"{idx}. {d.name} ({d.duration_days}d)")
                drill_choice = 0
                while drill_choice < 1 or drill_choice > len(camp.available_drills):
                    try:
                        drill_choice = int(input("Select drill: "))
                    except ValueError:
                        pass
                drill = camp.available_drills[drill_choice - 1]

                intensity = input("Intensity (light/moderate/intense): ").lower()
                if intensity not in ("light", "moderate", "intense"):
                    intensity = "moderate"

                if training.start_camp(camp, drill, intensity, finance):
                    print(f"Started {camp.name} with {drill.name}")
                else:
                    print("Failed to start camp.")

            elif tc == "2":
                if not training.current_camp:
                    print("No active camp!")
                    continue
                result = training.train_day()
                if result["status"] == "training":
                    gains = result.get("gains", {})
                    if gains:
                        print(f"Training gains: {', '.join(f'{a}: {v:+.1f}' for a, v in gains.items())}")
                    print(f"Fatigue: {result['fatigue']:.0%}")
                    if result.get("injury"):
                        print(f"INJURY: {result['injury']['type']} ({result['injury']['recovery_days']}d)")
                    if result.get("camp_over"):
                        print("Camp complete!")
                    if result.get("drill_over"):
                        print("Drill complete! Start a new drill or end camp.")
                else:
                    print("No training happening.")

            elif tc == "3":
                training.end_camp()
                print("Camp ended.")

        elif choice == "2":
            if current_fight_booking:
                print("You already have a fight booked!")
                continue
            if not career.current_promotion:
                print("You're not signed with any promotion!")
                continue
            if not fighter.is_available():
                print("You're injured or suspended! Cannot fight.")
                continue

            promo = career.current_promotion
            opponents = promo.get_available_opponents(fighter)

            if not opponents:
                print("No available opponents in your weight class.")
                continue

            print(f"\n=== Book Fight ===")
            print(f"Weight class: {fighter.weight_class}")
            print("Available opponents:")
            for idx, (opp, difficulty) in enumerate(opponents, 1):
                rec = opp.get_record_string()
                streak = f"W{opp.win_streak}" if opp.win_streak > 0 else (f"L{opp.loss_streak}" if opp.loss_streak > 0 else "")
                print(f"{idx}. {opp.name:25s} ({rec}) Rank #{opp.rank} [{difficulty}] {streak}")

            opp_choice = 0
            while opp_choice < 1 or opp_choice > len(opponents):
                try:
                    opp_choice = int(input("Select opponent: "))
                except ValueError:
                    pass
            opponent = opponents[opp_choice - 1][0]

            fight_date = datetime.now() + timedelta(weeks=8)
            event_name = f"Fight Night: {fighter.name} vs {opponent.name}"
            event = event_sys.create_event(event_name, fight_date, promo)
            fight_book = event_sys.book_fight(event, fighter, opponent)
            event_sys.generate_card(event, fighter, promo)

            if fight_book:
                current_event = event
                current_fight_booking = fight_book
                rivalry = career.add_rivalry(opponent)
                print(f"\nFight booked! {fighter.name} vs {opponent.name}")
                print(f"Date: {fight_date.strftime('%Y-%m-%d')}")
                print(f"Promotion: {promo.name}")
                print(f"Contract: {career.contract.get_details() if career.contract else 'No contract'}")
            else:
                print("Failed to book fight.")

        elif choice == "3":
            if not current_fight_booking:
                print("No fight booked! Book a fight first.")
                continue

            event = current_event
            fight_book = current_fight_booking
            opponent = fight_book.fighter2 if fight_book.fighter1 == fighter else fight_book.fighter1

            if not fighter.is_available():
                print("You're not medically cleared! Cannot fight.")
                continue

            result = run_fight_night(fighter, opponent, career, training, finance, health, media,
                                     event_sys, event, fight_book)

            won = result.get("winner") == fighter.name
            method = result.get("method", "Decision")
            win_round = result.get("round")

            fight_book.complete(fighter if won else opponent, method, win_round)

            fighter.shake_ring_rust()
            opponent.shake_ring_rust()

            if career.contract:
                pay_info = finance.add_fight_pay(
                    career.contract.base_pay if not won else career.contract.base_pay,
                    career.contract.win_bonus if won else 0,
                    perf_bonus=0
                )
                career.contract.complete_fight(won, False)
                career.career_earnings += pay_info["net"]
                print(f"\nFight purse: {utils.format_currency(pay_info['gross'])}")
                if pay_info["agent_cut"] > 0:
                    print(f"Agent cut: {utils.format_currency(pay_info['agent_cut'])}")
                print(f"Net earnings: {utils.format_currency(pay_info['net'])}")

            if career.contract and career.contract.is_expired():
                print("\nYour contract has expired! You're now a free agent.")
                print("Look for a new contract in the Career menu.")
                career.current_promotion = None
                career.contract = None

            promo = career.current_promotion
            if promo and fighter.rank <= 2 and not promo.champions.get(fighter.weight_class):
                print(f"\n*** You're ranked #{fighter.rank}! A title shot is next! ***")
                is_title = True
            elif promo and promo.champions.get(fighter.weight_class) == fighter:
                print(f"\n*** YOU ARE THE CHAMPION! Title defenses: {career.title_defenses} ***")

            promo_offer = career.check_promotion_offer() if not is_title else None
            if promo_offer and won:
                print(f"\n*** {promo_offer.name} is interested in signing you! ***")
                resp = input(f"Sign with {promo_offer.name}? (y/n): ").lower()
                if resp == "y":
                    career.sign_with_promotion(promo_offer, 4)
                    print(f"Signed with {promo_offer.name}!")
                    print(f"New contract: {career.contract.get_details()}")

            current_event = None
            current_fight_booking = None

        elif choice == "4":
            print(f"\n=== Career Stats ===")
            summary = career.get_summary()
            print(f"Record: {summary['record']}")
            print(f"Peak Rank: #{summary['peak_rank']}")
            print(f"Current Rank: #{summary['rank']}")
            print(f"Promotion: {summary['promotion']}")
            print(f"Title Defenses: {summary['title_defenses']}")
            print(f"Career Earnings: {utils.format_currency(summary['career_earnings'])}")
            print(f"Age: {summary['age']}")
            print(f"Rating: {fighter.get_overall_rating():.1f}")
            print(f"Archetype: {fighter.archetype}")
            print(f"Background: {fighter.background}")
            print(f"Weight: {fighter.current_weight_lbs}lbs ({fighter.weight_class})")
            print(f"Height: {fighter.height}in, Reach: {fighter.reach}in")
            print(f"Win Streak: {fighter.win_streak}, Loss Streak: {fighter.loss_streak}")
            print(f"Confidence: {fighter.confidence:.0f}")

            if career.contract:
                print(f"\nContract: {career.contract.get_details()}")
            else:
                print("\nContract: Free Agent")

            rivalries = career.get_rivalry_summary()
            if rivalries:
                print(f"\nRivalries ({len(rivalries)}):")
                for r in rivalries:
                    print(f"  {r}")

            print(f"\nTop Physical Attributes:")
            for attr in fighter.PHYSICAL_ATTRS[:5]:
                print(f"  {attr}: {fighter.attributes[attr]:.0f}")
            print(f"Top Mental Attributes:")
            for attr in fighter.MENTAL_ATTRS[:3]:
                print(f"  {attr}: {fighter.attributes[attr]:.0f}")

            injuries = health.get_active_injuries()
            if injuries:
                print(f"\nInjuries:")
                for i in injuries:
                    print(f"  {i['type']} (severity: {i['severity']:.1f})")
            susp_days = health.get_medical_suspension_days()
            if susp_days > 0:
                print(f"Medical Suspension: {susp_days} days remaining")

            input("\nPress Enter to continue...")

        elif choice == "5":
            print(f"\n=== Finances ===")
            fin = finance.get_summary()
            print(f"Net Worth: {utils.format_currency(fin['net_worth'])}")
            print(f"Agent: {fin['agent']}")
            print(f"Gym: {fin['gym']}")
            print(f"Monthly Sponsorship: {utils.format_currency(fin['monthly_income'])}")
            print(f"Monthly Living Expense: {utils.format_currency(1000)}")
            if fighter.gym:
                for g in utils.GYMS:
                    if g["name"] == fighter.gym:
                        print(f"Gym Membership: {utils.format_currency(g['monthly_fee'])}/mo")
                        break

            print(f"\nRecent Transactions:")
            recent = [t for t in finance.transactions if (datetime.now() - t.date).days <= 90]
            for t in recent[-10:]:
                sign = "+" if t.amount > 0 else ""
                print(f"  {sign}{utils.format_currency(t.amount):>12s} | {t.description}")

            if finance.consecutive_broke_months >= 12:
                print(f"\nWARNING: Broke for {finance.consecutive_broke_months} months!")
                print("You'll be forced to retire if this continues.")

            input("\nPress Enter to continue...")

        elif choice == "6":
            print(f"\n=== Personal ===")
            print(f"1. Join/Leave Gym (Current: {fighter.gym or 'None'})")
            print(f"2. Hire/Fire Agent (Current: {fighter.agent or 'None'})")
            print(f"3. Change Weight Class (Current: {fighter.weight_class})")
            print(f"4. Set Fight Speed (Current: {FIGHT_SPEED}s)")
            pc = input("Choice: ")

            if pc == "1":
                if fighter.gym:
                    print(f"Current gym: {fighter.gym}")
                    resp = input("Leave this gym? (y/n): ")
                    if resp == "y":
                        fighter.gym = None
                        print("Left gym.")
                else:
                    print("\nAvailable gyms:")
                    for idx, g in enumerate(utils.GYMS, 1):
                        specs = ", ".join(g["specialties"])
                        print(f"{idx}. {g['name']} ({specs}) - {utils.format_currency(g['monthly_fee'])}/mo")
                    gym_choice = 0
                    while gym_choice < 1 or gym_choice > len(utils.GYMS):
                        try:
                            gym_choice = int(input("Select gym: "))
                        except ValueError:
                            pass
                    chosen_gym = utils.GYMS[gym_choice - 1]
                    if finance.can_afford(chosen_gym["monthly_fee"]):
                        fighter.gym = chosen_gym["name"]
                        print(f"Joined {chosen_gym['name']}!")
                    else:
                        print("Can't afford the membership fee!")

            elif pc == "2":
                if fighter.agent:
                    print(f"Current agent: {fighter.agent}")
                    resp = input("Fire agent? (y/n): ")
                    if resp == "y":
                        finance.fire_agent()
                        print("Agent fired.")
                else:
                    print("\nAvailable agents:")
                    for idx, a in enumerate(utils.AGENTS, 1):
                        print(f"{idx}. {a['name']} - {a['cut']*100:.0f}% cut, +{a['negotiation_bonus']*100:.0f}% contracts")
                        print(f"     {a['perks']}")
                    agent_choice = 0
                    while agent_choice < 1 or agent_choice > len(utils.AGENTS):
                        try:
                            agent_choice = int(input("Select agent: "))
                        except ValueError:
                            pass
                    chosen_agent = utils.AGENTS[agent_choice - 1]
                    if finance.hire_agent(chosen_agent["name"]):
                        print(f"Hired {chosen_agent['name']}!")
                    else:
                        print("Failed to hire agent.")

            elif pc == "3":
                print("\nWeight classes:")
                for i, wc in enumerate(utils.WEIGHT_CLASSES, 1):
                    print(f"{i}. {wc['name']} ({wc['min']}-{wc['max']} lbs)")
                wc_choice = 0
                while wc_choice < 1 or wc_choice > len(utils.WEIGHT_CLASSES):
                    try:
                        wc_choice = int(input("Select new weight class: "))
                    except ValueError:
                        pass
                new_wc = utils.WEIGHT_CLASSES[wc_choice - 1]
                new_weight = random.randint(new_wc["min"], new_wc["max"])
                old_class = fighter.weight_class
                fighter.adjust_weight(new_weight)
                print(f"Changed weight class from {old_class} to {fighter.weight_class}!")
                print(f"New weight: {new_weight}lbs")
                if career.current_promotion:
                    career.current_promotion.update_rankings()

            elif pc == "4":
                try:
                    FIGHT_SPEED = float(input("Enter fight speed in seconds (0.2-3.0): "))
                    FIGHT_SPEED = max(0.2, min(3.0, FIGHT_SPEED))
                except ValueError:
                    pass
                print(f"Fight speed set to {FIGHT_SPEED}s")

        elif choice == "7":
            print(f"\n=== Advance Time ===")
            print("1. 1 Day")
            print("2. 1 Week")
            print("3. 1 Month")
            at = input("Choice: ")

            days = 0
            if at == "1":
                days = 1
            elif at == "2":
                days = 7
            elif at == "3":
                days = 30
            else:
                continue

            event_sys.advance_time(datetime.now() + timedelta(days=days))
            fighter.months_inactive += days // 30
            if days >= 7:
                fighter.apply_skill_decay()
            if days >= 30:
                finance.process_monthly()
                for months in range(days // 30):
                    fighter.monthly_aging()
                health.recover()

            if current_fight_booking and current_event:
                fight_date = current_fight_booking.date
                if datetime.now() >= fight_date:
                    print(f"\nYour fight date has arrived! Go to Fight Night!")
                else:
                    remaining = (fight_date - datetime.now()).days
                    print(f"\nDays until fight: {remaining}")

            print(f"Advanced {days} day(s).")

        elif choice == "8":
            print("\n1. Save & Exit")
            print("2. Retire")
            print("3. Just Exit (no save)")
            ex = input("Choice: ")
            if ex == "2":
                if career.try_retire(force=True):
                    print(f"{fighter.name} has retired!")
                    print(f"Final Record: {fighter.get_record_string()}")
                    print(f"Career Earnings: {utils.format_currency(career.career_earnings)}")
                    print(f"Peak Rank: #{fighter.peak_rank}")
                    break
            elif ex == "1" or ex == "3":
                print("Goodbye!")
                break

        if finance.consecutive_broke_months >= 12 and finance.net_worth < 0:
            print(f"\n{fighter.name} has been broke for 12 consecutive months.")
            print("Forced into retirement.")
            break

    print("\n" + "=" * 50)
    print("GAME OVER")
    print("=" * 50)
    print(f"{fighter.name}'s MMA Career")
    print(f"Record: {fighter.get_record_string()}")
    print(f"Peak Rank: #{fighter.peak_rank}")
    print(f"Title Defenses: {career.title_defenses}")
    print(f"Career Earnings: {utils.format_currency(career.career_earnings)}")
    print(f"Rivalries: {len(career.rivalries)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
    except EOFError:
        print("\n\nGoodbye!")
        sys.exit(0)
