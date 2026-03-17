"""Fitness goal tracking and recommendation service."""

from datetime import date, timedelta
from models.database import db, User, FitnessData, BodyMetric, FoodEntry


class FitnessService:
    """Tracks fitness progress against goals and provides recommendations."""

    def get_daily_status(self, user_id, target_date=None):
        """Get comprehensive daily fitness status with goal progress."""
        target = target_date or date.today()
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        fitness = FitnessData.query.filter_by(
            user_id=user_id, date=target
        ).first()

        food_entries = FoodEntry.query.filter_by(
            user_id=user_id, date=target
        ).all()

        body = BodyMetric.query.filter_by(
            user_id=user_id, date=target
        ).first()

        # Calculate calorie balance
        calories_in = sum(e.calories or 0 for e in food_entries)
        calories_out = (fitness.total_calories_burned or 0) if fitness else 0
        bmr = user.get_bmr() or 0
        total_expenditure = calories_out if calories_out > bmr else bmr + (calories_out * 0.5)
        calorie_balance = calories_in - total_expenditure

        # Determine if on track for goal
        target_balance = self._get_target_balance(user)

        status = {
            "date": target.isoformat(),
            "user_goal": user.goal_type,
            "calories": {
                "consumed": round(calories_in),
                "burned": round(total_expenditure),
                "target": user.daily_calorie_target or round(user.get_tdee() or 2000),
                "balance": round(calorie_balance),
                "target_balance": target_balance,
                "on_track": self._is_calorie_on_track(
                    calorie_balance, target_balance, user.goal_type),
            },
            "macros": self._get_macro_status(user, food_entries),
            "activity": self._get_activity_status(user, fitness),
            "body": self._get_body_status(user, body),
            "recovery": self._get_recovery_status(fitness),
            "recommendations": [],
        }

        status["recommendations"] = self._generate_recommendations(status, user)
        status["overall_score"] = self._calculate_daily_score(status)

        return status

    def _get_target_balance(self, user):
        """Determine target calorie balance based on goal."""
        goals = {
            "lose_weight": -500,     # 500 cal deficit for ~0.5kg/week loss
            "gain_muscle": 300,      # 300 cal surplus for lean gains
            "maintain": 0,
            "improve_endurance": -200,  # slight deficit while training
        }
        return goals.get(user.goal_type, 0)

    def _is_calorie_on_track(self, balance, target, goal):
        """Check if calorie balance aligns with goal."""
        tolerance = 200  # allow 200 cal deviation
        return abs(balance - target) <= tolerance

    def _get_macro_status(self, user, entries):
        """Calculate macro status against targets."""
        totals = {
            "protein_g": sum(e.protein_g or 0 for e in entries),
            "carbs_g": sum(e.carbs_g or 0 for e in entries),
            "fat_g": sum(e.fat_g or 0 for e in entries),
        }

        targets = {
            "protein_g": user.daily_protein_g or 130,
            "carbs_g": user.daily_carbs_g or 250,
            "fat_g": user.daily_fat_g or 65,
        }

        macros = {}
        for macro, current in totals.items():
            target = targets[macro]
            pct = (current / target * 100) if target > 0 else 0
            name = macro.replace("_g", "").title()
            macros[macro] = {
                "current": round(current, 1),
                "target": target,
                "percentage": round(pct, 1),
                "status": "good" if 80 <= pct <= 120 else ("low" if pct < 80 else "high"),
                "name": name,
            }

        return macros

    def _get_activity_status(self, user, fitness):
        """Evaluate activity level against recommendations."""
        if not fitness:
            return {
                "steps": {"current": 0, "target": 10000, "status": "no_data"},
                "exercise_minutes": {"current": 0, "target": 30, "status": "no_data"},
            }

        steps_target = 10000
        exercise_target = 30  # WHO recommends 150 min/week = ~21 min/day

        return {
            "steps": {
                "current": fitness.steps or 0,
                "target": steps_target,
                "percentage": round((fitness.steps or 0) / steps_target * 100, 1),
                "status": "good" if (fitness.steps or 0) >= steps_target else "low",
            },
            "exercise_minutes": {
                "current": fitness.exercise_minutes or 0,
                "target": exercise_target,
                "percentage": round((fitness.exercise_minutes or 0) / exercise_target * 100, 1),
                "status": "good" if (fitness.exercise_minutes or 0) >= exercise_target else "low",
            },
            "strain_score": fitness.strain_score,
        }

    def _get_body_status(self, user, body):
        """Evaluate body metrics against goals."""
        if not body:
            return {"status": "no_data"}

        status = {
            "weight_kg": body.weight_kg,
            "body_fat_pct": body.body_fat_pct,
            "muscle_mass_kg": body.muscle_mass_kg,
        }

        if user.target_weight_kg and body.weight_kg:
            diff = body.weight_kg - user.target_weight_kg
            status["weight_to_goal"] = round(diff, 1)
            status["weight_status"] = (
                "at_goal" if abs(diff) < 1
                else "above_goal" if diff > 0
                else "below_goal"
            )

        return status

    def _get_recovery_status(self, fitness):
        """Evaluate recovery metrics."""
        if not fitness or not fitness.recovery_score:
            return {"status": "no_data"}

        score = fitness.recovery_score
        return {
            "recovery_score": score,
            "hrv_ms": fitness.hrv_ms,
            "resting_heart_rate": fitness.resting_heart_rate,
            "sleep_hours": fitness.sleep_hours,
            "status": (
                "excellent" if score >= 67
                else "moderate" if score >= 34
                else "poor"
            ),
            "recommendation": (
                "Great recovery! Push hard today." if score >= 67
                else "Moderate recovery. Consider lighter activity." if score >= 34
                else "Low recovery. Prioritize rest and sleep."
            ),
        }

    def _generate_recommendations(self, status, user):
        """Generate actionable recommendations based on all data."""
        recs = []

        # Calorie recommendations
        cal = status["calories"]
        if user.goal_type == "lose_weight" and cal["balance"] > 0:
            excess = cal["balance"]
            recs.append({
                "category": "nutrition",
                "priority": "high",
                "message": f"You're {excess} cal over your deficit target. "
                           f"Consider a lighter dinner or add a 30-min walk.",
            })
        elif user.goal_type == "gain_muscle" and cal["balance"] < -200:
            deficit = abs(cal["balance"])
            recs.append({
                "category": "nutrition",
                "priority": "high",
                "message": f"You need ~{deficit} more calories to support muscle gain. "
                           f"Add a protein-rich snack.",
            })

        # Macro recommendations
        for macro, data in status["macros"].items():
            if data["status"] == "low" and data["percentage"] < 60:
                recs.append({
                    "category": "nutrition",
                    "priority": "medium",
                    "message": f"{data['name']} is low ({data['current']}g / {data['target']}g). "
                               f"Focus on {data['name'].lower()}-rich foods.",
                })

        # Activity recommendations
        activity = status["activity"]
        if activity.get("steps", {}).get("status") == "low":
            remaining = activity["steps"]["target"] - activity["steps"]["current"]
            recs.append({
                "category": "activity",
                "priority": "medium",
                "message": f"You need {remaining} more steps today. "
                           f"Consider a walk or taking stairs.",
            })

        # Recovery recommendations
        recovery = status["recovery"]
        if recovery.get("status") == "poor":
            recs.append({
                "category": "recovery",
                "priority": "high",
                "message": "Recovery is low. Prioritize sleep, hydration, and "
                           "consider light yoga or stretching instead of intense exercise.",
            })

        # Sleep recommendations
        sleep = recovery.get("sleep_hours")
        if sleep is not None and sleep < 7:
            recs.append({
                "category": "recovery",
                "priority": "high",
                "message": f"Only {sleep:.1f} hours of sleep. Aim for 7-9 hours. "
                           f"Try to get to bed earlier tonight.",
            })

        return recs

    def _calculate_daily_score(self, status):
        """Calculate an overall daily health score (0-100)."""
        scores = []

        # Calorie adherence (25% weight)
        cal = status["calories"]
        if cal["target"] > 0:
            cal_pct = min(100, max(0, 100 - abs(cal["consumed"] - cal["target"]) / cal["target"] * 100))
            scores.append(("nutrition", cal_pct, 0.25))

        # Macro balance (20% weight)
        macro_scores = []
        for macro, data in status["macros"].items():
            if data["target"] > 0:
                pct = min(100, max(0, 100 - abs(data["percentage"] - 100)))
                macro_scores.append(pct)
        if macro_scores:
            scores.append(("macros", sum(macro_scores) / len(macro_scores), 0.20))

        # Activity (20% weight)
        activity = status["activity"]
        if activity.get("steps", {}).get("target"):
            step_score = min(100, activity["steps"]["percentage"])
            scores.append(("activity", step_score, 0.20))

        # Recovery (20% weight)
        recovery = status["recovery"]
        if recovery.get("recovery_score") is not None:
            scores.append(("recovery", recovery["recovery_score"], 0.20))

        # Sleep (15% weight)
        if recovery.get("sleep_hours") is not None:
            sleep_score = min(100, recovery["sleep_hours"] / 8 * 100)
            scores.append(("sleep", sleep_score, 0.15))

        if not scores:
            return 0

        # Normalize weights
        total_weight = sum(s[2] for s in scores)
        return round(sum(s[1] * s[2] / total_weight for s in scores))

    def get_progress_report(self, user_id, days=7):
        """Generate a multi-day progress report."""
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        end = date.today()
        start = end - timedelta(days=days)

        daily_scores = []
        current = start
        while current <= end:
            status = self.get_daily_status(user_id, current)
            daily_scores.append({
                "date": current.isoformat(),
                "score": status.get("overall_score", 0),
                "calories_consumed": status["calories"]["consumed"],
                "calories_burned": status["calories"]["burned"],
            })
            current += timedelta(days=1)

        # Weight trend
        body_metrics = BodyMetric.query.filter(
            BodyMetric.user_id == user_id,
            BodyMetric.date >= start,
            BodyMetric.date <= end,
        ).order_by(BodyMetric.date).all()

        weight_trend = [{"date": b.date.isoformat(), "weight_kg": b.weight_kg}
                        for b in body_metrics if b.weight_kg]

        avg_score = (sum(d["score"] for d in daily_scores) / len(daily_scores)
                     if daily_scores else 0)

        return {
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "days": days,
            "avg_daily_score": round(avg_score),
            "daily_scores": daily_scores,
            "weight_trend": weight_trend,
            "goal": user.goal_type,
            "target_weight": user.target_weight_kg,
        }
