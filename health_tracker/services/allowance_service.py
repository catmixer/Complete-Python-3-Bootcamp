"""Weekly allowance and lifestyle budget service.

Manages what the user is "allowed" to do based on their fitness performance,
calorie budget, and health goals. Dynamically adjusts based on compliance.
"""

from datetime import date, timedelta
from models.database import db, User, WeeklyAllowance, FoodEntry, FitnessData


class AllowanceService:
    """Manages weekly allowances for lifestyle choices like dining out, drinks, etc."""

    # Standard drink definitions (alcohol units)
    DRINK_UNITS = {
        "gin and soda": 1.0,
        "gin and tonic": 1.0,
        "vodka soda": 1.0,
        "glass of wine": 1.5,
        "pint of beer": 2.0,
        "cocktail": 1.5,
        "shot": 1.0,
        "margarita": 1.5,
    }

    def get_current_week(self, user_id):
        """Get or create the current week's allowance record."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Monday

        allowance = WeeklyAllowance.query.filter_by(
            user_id=user_id, week_start=week_start
        ).first()

        if not allowance:
            allowance = WeeklyAllowance(
                user_id=user_id,
                week_start=week_start,
            )
            # Check if user earned bonuses from last week
            bonus = self._calculate_bonuses(user_id, week_start)
            allowance.bonus_alcohol_units = bonus.get("bonus_alcohol_units", 0)
            allowance.bonus_cheat_meals = bonus.get("bonus_cheat_meals", 0)
            allowance.adjustment_reason = bonus.get("reason", "")

            db.session.add(allowance)
            db.session.commit()

        return allowance

    def get_allowance_status(self, user_id):
        """Get full allowance status with what the user can still do this week."""
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        allowance = self.get_current_week(user_id)

        # Calculate remaining calorie budget for the week
        week_cal_status = self._get_weekly_calorie_status(user)

        # Determine what the user is allowed to do
        options = self._generate_options(user, allowance, week_cal_status)

        return {
            "week_start": allowance.week_start.isoformat(),
            "alcohol": {
                "total_allowed": user.weekly_alcohol_units + allowance.bonus_alcohol_units,
                "used": allowance.alcohol_units_used,
                "remaining": allowance.get_remaining_alcohol(),
                "bonus_earned": allowance.bonus_alcohol_units,
            },
            "cheat_meals": {
                "total_allowed": user.weekly_cheat_meals + allowance.bonus_cheat_meals,
                "used": allowance.cheat_meals_used,
                "remaining": allowance.get_remaining_cheat_meals(),
            },
            "rest_days": {
                "total_allowed": user.weekly_rest_days,
                "used": allowance.rest_days_used,
                "remaining": max(0, user.weekly_rest_days - allowance.rest_days_used),
            },
            "dining_out": {
                "count_this_week": allowance.dining_out_count,
            },
            "calorie_budget": week_cal_status,
            "options": options,
            "adjustment_reason": allowance.adjustment_reason,
        }

    def use_allowance(self, user_id, allowance_type, amount=1):
        """Record usage of an allowance."""
        allowance = self.get_current_week(user_id)

        if allowance_type == "alcohol":
            allowance.alcohol_units_used += amount
        elif allowance_type == "cheat_meal":
            allowance.cheat_meals_used += amount
        elif allowance_type == "rest_day":
            allowance.rest_days_used += amount
        elif allowance_type == "dining_out":
            allowance.dining_out_count += amount

        db.session.commit()
        return self.get_allowance_status(user_id)

    def _get_weekly_calorie_status(self, user):
        """Calculate calorie budget status for the current week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        days_elapsed = (today - week_start).days + 1
        days_remaining = 7 - days_elapsed

        daily_target = user.daily_calorie_target or round(user.get_tdee() or 2000)
        weekly_target = daily_target * 7

        # Sum calories consumed this week
        entries = FoodEntry.query.filter(
            FoodEntry.user_id == user.id,
            FoodEntry.date >= week_start,
            FoodEntry.date <= today,
        ).all()
        consumed = sum(e.calories or 0 for e in entries)

        remaining = weekly_target - consumed
        daily_remaining = remaining / days_remaining if days_remaining > 0 else 0

        return {
            "weekly_target": weekly_target,
            "consumed_so_far": round(consumed),
            "remaining": round(remaining),
            "days_remaining": days_remaining,
            "daily_budget_remaining": round(daily_remaining),
            "on_track": consumed <= daily_target * days_elapsed * 1.1,
        }

    def _generate_options(self, user, allowance, cal_status):
        """Generate specific options for what the user can do."""
        options = []
        remaining_alcohol = allowance.get_remaining_alcohol()
        remaining_cheats = allowance.get_remaining_cheat_meals()
        daily_budget = cal_status["daily_budget_remaining"]

        # Dining out options
        if remaining_cheats > 0 and daily_budget > 500:
            options.append({
                "type": "dining_out",
                "title": "Dining Out",
                "description": f"You can eat out {remaining_cheats} more time(s) this week",
                "budget": f"Keep your meal under {min(daily_budget, 800)} calories",
                "tips": [
                    "Choose grilled over fried",
                    "Ask for dressing on the side",
                    "Skip the bread basket",
                    "Have a salad or soup as a starter",
                ],
            })

        # Alcohol options
        if remaining_alcohol > 0:
            drink_options = []
            for drink, units in self.DRINK_UNITS.items():
                max_drinks = int(remaining_alcohol / units)
                if max_drinks > 0:
                    drink_options.append({
                        "drink": drink,
                        "max_quantity": max_drinks,
                        "units_each": units,
                    })

            if drink_options:
                options.append({
                    "type": "alcohol",
                    "title": "Alcohol Budget",
                    "description": f"You have {remaining_alcohol} alcohol units remaining this week",
                    "drink_options": drink_options,
                    "tips": [
                        "Have drinks with meals, not on empty stomach",
                        "Alternate with water between drinks",
                        "Choose lower-calorie mixers (soda water > tonic)",
                        "Avoid sugary cocktails",
                    ],
                    "example": self._generate_drink_example(remaining_alcohol),
                })

        # Treat options
        if daily_budget > 200:
            options.append({
                "type": "treat",
                "title": "Treat Budget",
                "description": f"You have ~{round(daily_budget - 200)} extra calories for a treat today",
                "suggestions": self._get_treat_suggestions(daily_budget - 200),
            })

        # Rest day options
        rest_remaining = max(0, user.weekly_rest_days - allowance.rest_days_used)
        if rest_remaining > 0:
            options.append({
                "type": "rest_day",
                "title": "Rest Days",
                "description": f"You can take {rest_remaining} more rest day(s) this week",
                "tips": [
                    "Light walking or yoga is still beneficial",
                    "Focus on sleep quality and hydration",
                    "Use rest days for meal prep",
                ],
            })

        # If budget is tight, add restriction notice
        if daily_budget < 300:
            options.append({
                "type": "restriction",
                "title": "Budget Alert",
                "description": "Your calorie budget is tight for the rest of the week",
                "recommendation": "Stick to lean proteins, vegetables, and whole grains. "
                                  "Save any treats or dining out for next week.",
            })

        return options

    def _generate_drink_example(self, remaining_units):
        """Generate a specific example of what the user can drink."""
        if remaining_units >= 2:
            return ("You could go out once this week and have "
                    f"2 gin and soda drinks (2 units)")
        elif remaining_units >= 1:
            return ("You could have 1 glass of wine or "
                    "1 gin and soda this week")
        else:
            return "Consider skipping alcohol this week to stay on track"

    def _get_treat_suggestions(self, calorie_budget):
        """Suggest treats that fit within the calorie budget."""
        treats = [
            {"name": "Dark chocolate (2 squares)", "calories": 90},
            {"name": "Frozen yogurt (small)", "calories": 150},
            {"name": "Protein cookie", "calories": 200},
            {"name": "Small popcorn", "calories": 120},
            {"name": "Fruit smoothie", "calories": 180},
            {"name": "Rice cakes with almond butter", "calories": 160},
            {"name": "Small ice cream scoop", "calories": 140},
            {"name": "Cheese and crackers", "calories": 200},
        ]
        return [t for t in treats if t["calories"] <= calorie_budget]

    def _calculate_bonuses(self, user_id, current_week_start):
        """Calculate bonus allowances based on last week's performance."""
        last_week_start = current_week_start - timedelta(days=7)
        last_week_end = current_week_start - timedelta(days=1)

        user = User.query.get(user_id)
        if not user:
            return {}

        # Check last week's calorie compliance
        entries = FoodEntry.query.filter(
            FoodEntry.user_id == user_id,
            FoodEntry.date >= last_week_start,
            FoodEntry.date <= last_week_end,
        ).all()

        if not entries:
            return {}

        daily_target = user.daily_calorie_target or round(user.get_tdee() or 2000)
        weekly_target = daily_target * 7
        total_consumed = sum(e.calories or 0 for e in entries)

        # Check exercise compliance
        fitness_records = FitnessData.query.filter(
            FitnessData.user_id == user_id,
            FitnessData.date >= last_week_start,
            FitnessData.date <= last_week_end,
        ).all()
        workout_days = sum(1 for f in fitness_records
                          if (f.exercise_minutes or 0) >= 20)

        bonus = {"bonus_alcohol_units": 0, "bonus_cheat_meals": 0, "reason": ""}
        reasons = []

        # Reward calorie compliance
        if total_consumed <= weekly_target * 1.05:  # within 5% of target
            bonus["bonus_alcohol_units"] += 1
            reasons.append("Great calorie management last week (+1 drink unit)")

        # Reward exercise consistency
        if workout_days >= 4:
            bonus["bonus_alcohol_units"] += 0.5
            bonus["bonus_cheat_meals"] += 1
            reasons.append(f"Excellent workout consistency ({workout_days} days, +1 cheat meal)")

        bonus["reason"] = "; ".join(reasons)
        return bonus
