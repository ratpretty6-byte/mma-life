from datetime import datetime
from typing import Dict, List, Optional

import utils
from fighter import Fighter


class Transaction:
    def __init__(self, amount: float, category: str, description: str, date: datetime = None, game_date: datetime = None):
        self.amount = amount
        self.category = category
        self.description = description
        self.date = date or game_date or datetime.now()

MONTHLY_LIVING_EXPENSE = 1000.0
MANAGER_CUT_BASE = 0.10

class FinancialSystem:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.transactions: List[Transaction] = []
        self.net_worth = 0.0
        self.sponsorship_deal: Optional[Dict] = None
        self.investments: List[Dict] = []
        self.consecutive_broke_months = 0

    def add_income(self, amount: float, category: str, description: str, game_date: datetime = None):
        self.transactions.append(Transaction(amount, category, description, game_date=game_date))
        self.net_worth += amount
        self.fighter.net_worth = self.net_worth

    def add_expense(self, amount: float, category: str, description: str, game_date: datetime = None):
        self.transactions.append(Transaction(-amount, category, description, game_date=game_date))
        self.net_worth -= amount
        self.fighter.net_worth = self.net_worth

    def can_afford(self, amount: float) -> bool:
        return self.net_worth >= amount

    def add_fight_pay(self, base_pay: float, win_bonus: float, perf_bonus: float = 0.0,
                      ppv_points: float = 0.0, game_date: datetime = None) -> Dict:
        total = base_pay + win_bonus + perf_bonus + ppv_points
        agent_cut = 0.0
        if self.fighter.agent:
            for a in utils.AGENTS:
                if a["name"] == self.fighter.agent:
                    agent_cut = total * a["cut"]
                    break
        net = total - agent_cut
        self.add_income(net, "fight_purse", f"Fight purse (after agent fees): {utils.format_currency(net)}", game_date)
        if agent_cut > 0:
            self.add_expense(agent_cut, "agent_fees", f"Agent cut ({utils.format_currency(agent_cut)})", game_date)
        return {"gross": total, "agent_cut": agent_cut, "net": net}

    def add_performance_bonus(self, bonus_type: str, amount: float, game_date: datetime = None):
        self.add_income(amount, f"bonus_{bonus_type}", f"{bonus_type.replace('_', ' ').title()}: {utils.format_currency(amount)}", game_date)

    def sign_sponsorship(self, monthly_income: float, duration_months: int):
        self.sponsorship_deal = {
            "monthly_income": monthly_income,
            "remaining_months": duration_months
        }

    def add_ppv_revenue(self, ppv_buys: int, fighter_share: float = 0.02, game_date: datetime = None):
        revenue = ppv_buys * 49.99 * fighter_share
        self.add_income(revenue, "ppv_revenue", f"PPV revenue: {utils.format_currency(revenue)}", game_date)
        return revenue

    def apply_taxes(self, game_date: datetime = None) -> float:
        monthly_income = sum(t.amount for t in self.transactions
                              if t.category in ("fight_purse", "sponsorship", "bonus_fotn",
                                                "bonus_potn", "ppv_revenue", "merchandise")
                              and (game_date and (game_date - t.date).days <= 30))
        if monthly_income > 50000:
            tax = monthly_income * 0.30
            self.add_expense(tax, "taxes", f"Tax on {utils.format_currency(monthly_income)} income", game_date)
            return tax
        return 0.0

    def process_monthly(self, game_date: datetime = None):
        self.add_expense(MONTHLY_LIVING_EXPENSE, "living_expenses", "Monthly living expenses", game_date)

        if self.sponsorship_deal and self.sponsorship_deal["remaining_months"] > 0:
            self.add_income(self.sponsorship_deal["monthly_income"], "sponsorship", "Monthly sponsorship", game_date)
            self.sponsorship_deal["remaining_months"] -= 1
            if self.sponsorship_deal["remaining_months"] <= 0:
                self.sponsorship_deal = None

        if self.fighter.gym:
            for g in utils.GYMS:
                if g["name"] == self.fighter.gym:
                    self.add_expense(g["monthly_fee"], "gym_membership", f"Gym membership: {g['name']}", game_date)
                    break

        for inv in self.investments[:]:
            inv["months_remaining"] -= 1
            if inv["months_remaining"] <= 0:
                self.add_income(inv["amount"] * (1 + inv["return_rate"]), "investment", "Investment return", game_date)
                self.investments.remove(inv)

        # Apply taxes on monthly income
        self.apply_taxes(game_date)

        if self.net_worth < 0:
            self.consecutive_broke_months += 1
        else:
            self.consecutive_broke_months = 0

    def hire_agent(self, agent_name: str, game_date: datetime = None) -> bool:
        for a in utils.AGENTS:
            if a["name"] == agent_name:
                if self.fighter.agent:
                    self.fire_agent(game_date)
                self.fighter.agent = agent_name
                self.add_expense(500, "agent_retainer", f"Agent signing: {agent_name}", game_date)
                return True
        return False

    def fire_agent(self, game_date: datetime = None):
        if self.fighter.agent:
            self.add_expense(1000, "agent_retainer", f"Severance: {self.fighter.agent}", game_date)
            self.fighter.agent = None

    def get_sponsorship_tier(self, rank: int, popularity: float) -> Dict:
        if rank <= 10 and popularity >= 80:
            return {"monthly_income": 5000, "duration_months": 12}
        elif rank <= 50:
            return {"monthly_income": 2000, "duration_months": 6}
        else:
            return {"monthly_income": 500, "duration_months": 6}

    def get_summary(self, game_date: datetime = None) -> Dict:
        now = game_date or datetime.now()
        return {
            "net_worth": self.net_worth,
            "monthly_income": self.sponsorship_deal["monthly_income"] if self.sponsorship_deal else 0,
            "agent": self.fighter.agent or "None",
            "gym": self.fighter.gym or "None",
            "recent_transactions": len([t for t in self.transactions if (now - t.date).days <= 30])
        }
