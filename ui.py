from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.core.window import Window

from fighter import Fighter
from training import TrainingSystem, TrainingCamp, DRILLS
from promotion import Promotion
from career import CareerSystem
from finance import FinancialSystem
from health import HealthSystem
from media import MediaSystem
from events import EventSystem
from fight import Fight
from strategy import StrategySystem, STRATEGIES
import utils
from datetime import datetime, timedelta

Window.orientation = 'portrait'

class MMALifeApp(App):
    def build(self):
        self.fighter = None
        self.career = None
        self.training = None
        self.finance = None
        self.health = None
        self.media = None
        self.event_sys = None
        self.promo = None
        self.current_camp = None
        
        self.root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Top stats bar
        self.stats_bar = BoxLayout(orientation='horizontal', size_hint_y=0.15)
        self.stats_label = Label(text="No fighter loaded", halign='center', text_size=(Window.width-20, None))
        self.stats_bar.add_widget(self.stats_label)
        self.root.add_widget(self.stats_bar)
        
        # Middle content
        self.scroll = ScrollView(size_hint_y=0.7)
        self.content = GridLayout(cols=1, spacing=5, size_hint_y=None, padding=5)
        self.content.bind(minimum_height=self.content.setter('height'))
        self.scroll.add_widget(self.content)
        self.root.add_widget(self.scroll)
        
        # Bottom nav
        self.nav = GridLayout(cols=3, size_hint_y=0.15, spacing=5)
        self.btn_train = Button(text="Train", min_height=48)
        self.btn_fight = Button(text="Fight", min_height=48)
        self.btn_stats = Button(text="Stats", min_height=48)
        self.nav.add_widget(self.btn_train)
        self.nav.add_widget(self.btn_fight)
        self.nav.add_widget(self.btn_stats)
        self.root.add_widget(self.nav)
        
        self.btn_train.bind(on_press=lambda x: self.show_training())
        self.btn_fight.bind(on_press=lambda x: self.show_fight_menu())
        self.btn_stats.bind(on_press=lambda x: self.show_stats())
        
        # Check if fighter exists, if not show creation
        self.show_creation()
        return self.root
    
    def log(self, text: str):
        lbl = Label(text=text, size_hint_y=None, height=40, halign='left', text_size=(Window.width-40, None))
        self.content.add_widget(lbl)
        self.scroll.scroll_to(lbl)
    
    def update_stats_bar(self):
        if self.fighter:
            self.stats_label.text = f"{self.fighter.name} | {self.fighter.weight_class}\n{self.fighter.wins}-{self.fighter.losses}-{self.fighter.draws} | Rank: {self.fighter.rank}"
    
    def show_creation(self):
        self.content.clear_widgets()
        self.log("=== Create Fighter ===")
        
        layout = GridLayout(cols=2, spacing=5, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        # Name
        layout.add_widget(Label(text="Name:"))
        name_input = TextInput(multiline=False, size_hint_y=None, height=40)
        layout.add_widget(name_input)
        
        # Age
        layout.add_widget(Label(text="Age:"))
        age_input = TextInput(multiline=False, input_filter='int', size_hint_y=None, height=40)
        age_input.text = "25"
        layout.add_widget(age_input)
        
        # Weight
        layout.add_widget(Label(text="Weight (lbs):"))
        weight_input = TextInput(multiline=False, input_filter='int', size_hint_y=None, height=40)
        weight_input.text = "155"
        layout.add_widget(weight_input)
        
        # Background
        layout.add_widget(Label(text="Background:"))
        bg_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=120)
        for bg in ["mma", "wrestling", "bjj", "muay_thai", "boxing"]:
            btn = Button(text=bg.title(), size_hint_y=None, height=30)
            bg_layout.add_widget(btn)
        layout.add_widget(bg_layout)
        
        self.content.add_widget(layout)
        
        # Create button
        create_btn = Button(text="Create Fighter", size_hint_y=None, height=50)
        create_btn.bind(on_press=lambda x: self.create_fighter(
            name_input.text, int(age_input.text or 25), 
            float(weight_input.text or 155), "mma"
        ))
        self.content.add_widget(create_btn)
    
    def create_fighter(self, name, age, weight, bg):
        if not name:
            self.log("Please enter a name")
            return
        self.fighter = Fighter(name, age, weight, bg)
        self.career, self.training, self.finance, self.health, self.media, self.event_sys, self.promo = career, training, finance, health, media, event_sys, promo = setup_career(self.fighter)
        
        # Create rival
        self.rival = Fighter("Rival Fighter", 25, weight, "boxing")
        self.career.add_rivalry(self.rival)
        self.promo.sign_fighter(self.rival, 3)
        
        self.update_stats_bar()
        self.content.clear_widgets()
        self.log(f"Fighter {name} created!")
        self.log(f"Weight Class: {self.fighter.weight_class}")
        self.log("Ready to train or fight!")
    
    def show_training(self):
        if not self.fighter:
            self.log("Create a fighter first!")
            return
        self.content.clear_widgets()
        self.log("=== Training ===")
        
        if self.training.current_camp:
            self.log(f"Current: {self.training.current_camp.name}")
            self.log(f"Drill: {self.training.current_drill.name if self.training.current_drill else 'None'}")
            self.log(f"Days trained: {self.training.days_trained}")
            self.log(f"Fatigue: {self.training.fatigue:.2f}")
            
            train_btn = Button(text="Train Day", size_hint_y=None, height=50)
            train_btn.bind(on_press=lambda x: self.do_train_day())
            self.content.add_widget(train_btn)
            
            end_btn = Button(text="End Camp", size_hint_y=None, height=50)
            end_btn.bind(on_press=lambda x: self.end_camp())
            self.content.add_widget(end_btn)
        else:
            self.log("No active camp. Select a camp:")
            camps = [
                ("Muay Thai Camp", "muay_thai", 4, 5000, 0.2),
                ("BJJ Camp", "bjj", 4, 5000, 0.2),
                ("Wrestling Camp", "wrestling", 4, 5000, 0.2),
                ("MMA Camp", "mma", 6, 10000, 0.3)
            ]
            for name, camp_type, weeks, cost, bonus in camps:
                btn = Button(text=f"{name} ({weeks}w)", size_hint_y=None, height=40)
                btn.bind(on_press=lambda x, n=name, ct=camp_type, w=weeks, c=cost, b=bonus: self.select_camp(n, ct, w, c, b))
                self.content.add_widget(btn)
    
    def select_camp(self, name, camp_type, weeks, cost, bonus):
        camp = TrainingCamp(name, camp_type, weeks, cost, bonus)
        self.training.current_camp = camp
        self.content.clear_widgets()
        self.log(f"Selected: {name}")
        self.log("Now select a drill:")
        for drill in camp.available_drills:
            btn = Button(text=f"{drill.name} ({drill.duration_days}d)", size_hint_y=None, height=40)
            btn.bind(on_press=lambda x, d=drill: self.start_camp(d, "moderate"))
            self.content.add_widget(btn)
    
    def start_camp(self, drill, intensity):
        if self.training.current_camp:
            self.training.start_camp(self.training.current_camp, drill, intensity)
            self.log(f"Started {drill.name} at {self.training.current_camp.name}")
            self.show_training()
    
    def do_train_day(self):
        result = self.training.train_day()
        self.log(f"Trained! Gains: {result.get('gains', {})}")
        if result.get('injury'):
            self.log(f"Injured: {result['injury']['type']}")
        if result.get('camp_over') or result.get('drill_over'):
            self.log("Training complete!")
            self.training.end_camp()
    
    def end_camp(self):
        self.training.end_camp()
        self.log("Camp ended. Fatigue reduced.")
        self.show_training()
    
    def show_fight_menu(self):
        if not self.fighter:
            self.log("Create a fighter first!")
            return
        self.content.clear_widgets()
        self.log("=== Fight Menu ===")
        
        # Check for upcoming fights
        if self.event_sys.upcoming_events and self.event_sys.upcoming_events[0].fights:
            self.log("Upcoming fight vs Rival Fighter")
            fight_btn = Button(text="Simulate Fight", size_hint_y=None, height=50)
            fight_btn.bind(on_press=lambda x: self.simulate_fight())
            self.content.add_widget(fight_btn)
        else:
            book_btn = Button(text="Book Fight vs Rival", size_hint_y=None, height=50)
            book_btn.bind(on_press=lambda x: self.book_fight())
            self.content.add_widget(book_btn)
    
    def book_fight(self):
        event_date = datetime.now() + timedelta(weeks=8)
        event = self.event_sys.create_event(f"Fight Night: {self.fighter.name} vs Rival", event_date, self.promo)
        fight_booking = self.event_sys.book_fight(event, self.fighter, self.rival)
        if fight_booking:
            self.log(f"Fight booked vs Rival Fighter on {event_date.strftime('%Y-%m-%d')}")
        else:
            self.log("Booking failed")
        self.show_fight_menu()
    
    def simulate_fight(self):
        self.content.clear_widgets()
        self.log("Select strategy:")
        for idx, s in enumerate(STRATEGIES, 1):
            btn = Button(text=s['name'], size_hint_y=None, height=40)
            btn.bind(on_press=lambda x, strat=s: self.run_fight(strat['id']))
            self.content.add_widget(btn)
    
    def run_fight(self, strategy_id):
        strat_sys = StrategySystem(self.fighter)
        strat_sys.set_pre_fight_strategy(strategy_id)
        fight = Fight(self.fighter, self.rival, rounds=3)
        result = fight.simulate_fight()
        
        self.log(f"Result: {result['winner']} wins via {result['method']} (Round {result['round']})")
        
        # Complete the fight
        fight_booking = self.event_sys.upcoming_events[0].fights[0]
        fight_booking.complete(fight.winner, fight.win_method, fight.win_round)
        
        # Add payout
        if self.career.contract:
            won = (fight.winner == self.fighter)
            total_pay = self.career.contract.complete_fight(won, False)
            self.finance.add_income(total_pay, "fight_purse", f"Fight vs {self.rival.name}")
            self.log(f"Earned: ${total_pay:,.2f}")
        
        self.update_stats_bar()
        
        # Show play-by-play (last 5 entries)
        self.log("\n=== Play-by-Play ===")
        for line in result['log'][-5:]:
            self.log(line)
    
    def show_stats(self):
        if not self.fighter:
            self.log("Create a fighter first!")
            return
        self.content.clear_widgets()
        self.log(f"=== {self.fighter.name} Stats ===")
        self.log(f"Weight: {self.fighter.current_weight_lbs}lbs ({self.fighter.weight_class})")
        self.log(f"Record: {self.fighter.wins}-{self.fighter.losses}-{self.fighter.draws}")
        self.log(f"Rank: {self.fighter.rank}")
        self.log(f"Net Worth: ${self.finance.net_worth:,.2f}")
        self.log(f"Popularity: {self.media.popularity:.1f}")
        self.log(f"Injuries: {len(self.health.get_active_injuries())}")

def setup_career(fighter):
    promo = Promotion("Local Fight League", "regional", [fighter.weight_class], 1.0)
    career = CareerSystem(fighter)
    career.sign_with_promotion(promo, 3)
    training = TrainingSystem(fighter)
    finance = FinancialSystem(fighter)
    health = HealthSystem(fighter)
    media = MediaSystem(fighter)
    event_sys = EventSystem()
    return career, training, finance, health, media, event_sys, promo

if __name__ == "__main__":
    MMALifeApp().run()
