"""Nutrient analysis service - detects deficiencies and provides recommendations."""

from datetime import date, timedelta
from models.database import db, FoodEntry, User


# Recommended Daily Allowances (RDA) for adults
# Separate values for male and female where applicable
RDA = {
    "male": {
        "calories": 2500, "protein_g": 56, "carbs_g": 325, "fat_g": 78,
        "fiber_g": 38, "sugar_g": 36,  # max recommended
        "saturated_fat_g": 20,  # max recommended
        "sodium_mg": 2300,  # max recommended
        "potassium_mg": 3400, "calcium_mg": 1000, "iron_mg": 8,
        "magnesium_mg": 420, "zinc_mg": 11, "phosphorus_mg": 700,
        "vitamin_a_mcg": 900, "vitamin_b1_mg": 1.2, "vitamin_b2_mg": 1.3,
        "vitamin_b3_mg": 16, "vitamin_b6_mg": 1.3, "vitamin_b12_mcg": 2.4,
        "vitamin_c_mg": 90, "vitamin_d_mcg": 15, "vitamin_e_mg": 15,
        "vitamin_k_mcg": 120, "folate_mcg": 400, "water_ml": 3700,
    },
    "female": {
        "calories": 2000, "protein_g": 46, "carbs_g": 260, "fat_g": 62,
        "fiber_g": 25, "sugar_g": 25,
        "saturated_fat_g": 16,
        "sodium_mg": 2300,
        "potassium_mg": 2600, "calcium_mg": 1000, "iron_mg": 18,
        "magnesium_mg": 320, "zinc_mg": 8, "phosphorus_mg": 700,
        "vitamin_a_mcg": 700, "vitamin_b1_mg": 1.1, "vitamin_b2_mg": 1.1,
        "vitamin_b3_mg": 14, "vitamin_b6_mg": 1.3, "vitamin_b12_mcg": 2.4,
        "vitamin_c_mg": 75, "vitamin_d_mcg": 15, "vitamin_e_mg": 15,
        "vitamin_k_mcg": 90, "folate_mcg": 400, "water_ml": 2700,
    },
}

# Nutrients where exceeding RDA is a concern (max limits)
MAX_NUTRIENTS = {"sodium_mg", "sugar_g", "saturated_fat_g"}

# Friendly names for nutrients
NUTRIENT_NAMES = {
    "calories": "Calories", "protein_g": "Protein", "carbs_g": "Carbohydrates",
    "fat_g": "Total Fat", "fiber_g": "Fiber", "sugar_g": "Sugar",
    "saturated_fat_g": "Saturated Fat", "sodium_mg": "Sodium",
    "potassium_mg": "Potassium", "calcium_mg": "Calcium", "iron_mg": "Iron",
    "magnesium_mg": "Magnesium", "zinc_mg": "Zinc",
    "phosphorus_mg": "Phosphorus", "vitamin_a_mcg": "Vitamin A",
    "vitamin_b1_mg": "Vitamin B1 (Thiamine)",
    "vitamin_b2_mg": "Vitamin B2 (Riboflavin)",
    "vitamin_b3_mg": "Vitamin B3 (Niacin)", "vitamin_b6_mg": "Vitamin B6",
    "vitamin_b12_mcg": "Vitamin B12", "vitamin_c_mg": "Vitamin C",
    "vitamin_d_mcg": "Vitamin D", "vitamin_e_mg": "Vitamin E",
    "vitamin_k_mcg": "Vitamin K", "folate_mcg": "Folate",
    "water_ml": "Water",
}

# Food sources for each nutrient
FOOD_SOURCES = {
    "protein_g": ["chicken breast", "salmon", "eggs", "greek yogurt", "tofu", "lentils"],
    "fiber_g": ["oats", "broccoli", "avocado", "beans", "berries", "sweet potato"],
    "calcium_mg": ["greek yogurt", "milk", "cheese", "spinach", "tofu", "almonds"],
    "iron_mg": ["red meat", "spinach", "lentils", "tofu", "fortified cereals"],
    "magnesium_mg": ["almonds", "spinach", "dark chocolate", "avocado", "bananas"],
    "zinc_mg": ["oysters", "beef", "pumpkin seeds", "lentils", "chickpeas"],
    "potassium_mg": ["banana", "sweet potato", "spinach", "avocado", "coconut water"],
    "vitamin_a_mcg": ["sweet potato", "carrots", "spinach", "kale", "eggs"],
    "vitamin_b12_mcg": ["salmon", "beef", "eggs", "fortified cereals", "nutritional yeast"],
    "vitamin_c_mg": ["oranges", "strawberries", "bell peppers", "broccoli", "kiwi"],
    "vitamin_d_mcg": ["salmon", "fortified milk", "egg yolks", "mushrooms", "sunlight"],
    "vitamin_e_mg": ["almonds", "sunflower seeds", "spinach", "avocado", "olive oil"],
    "vitamin_k_mcg": ["kale", "spinach", "broccoli", "brussels sprouts", "green beans"],
    "folate_mcg": ["lentils", "spinach", "asparagus", "broccoli", "avocado"],
    "vitamin_b6_mg": ["chicken", "salmon", "banana", "potatoes", "chickpeas"],
    "water_ml": ["water", "herbal tea", "cucumber", "watermelon", "coconut water"],
}


class NutrientService:
    """Service for analyzing nutrient intake and detecting deficiencies."""

    def get_rda(self, user):
        """Get personalized RDA based on user profile."""
        gender = user.gender or "male"
        base_rda = dict(RDA.get(gender, RDA["male"]))

        # Override with user's custom targets if set
        if user.daily_calorie_target:
            base_rda["calories"] = user.daily_calorie_target
        if user.daily_protein_g:
            base_rda["protein_g"] = user.daily_protein_g
        if user.daily_carbs_g:
            base_rda["carbs_g"] = user.daily_carbs_g
        if user.daily_fat_g:
            base_rda["fat_g"] = user.daily_fat_g
        if user.daily_fiber_g:
            base_rda["fiber_g"] = user.daily_fiber_g
        if user.daily_water_ml:
            base_rda["water_ml"] = user.daily_water_ml

        # Adjust based on activity level
        activity_multipliers = {
            "sedentary": 0.9, "light": 1.0, "moderate": 1.1,
            "active": 1.2, "very_active": 1.3,
        }
        multiplier = activity_multipliers.get(user.activity_level, 1.0)

        # Scale calorie-dependent nutrients
        for key in ["calories", "protein_g", "carbs_g", "fat_g"]:
            if key in base_rda and not getattr(user, f"daily_{key}" if key != "calories" else "daily_calorie_target", None):
                base_rda[key] = round(base_rda[key] * multiplier)

        return base_rda

    def analyze_daily(self, user_id, target_date=None):
        """Analyze today's nutrient intake against RDA."""
        target = target_date or date.today()
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        rda = self.get_rda(user)

        entries = FoodEntry.query.filter_by(
            user_id=user_id, date=target
        ).all()

        # Sum intake
        intake = {}
        for key in rda:
            intake[key] = sum(getattr(e, key, 0) or 0 for e in entries)

        # Analyze each nutrient
        analysis = {
            "date": target.isoformat(),
            "intake": intake,
            "targets": rda,
            "nutrients": {},
            "deficiencies": [],
            "excesses": [],
            "on_track": [],
        }

        for nutrient, target_val in rda.items():
            if target_val == 0:
                continue

            current = intake.get(nutrient, 0)
            pct = (current / target_val * 100) if target_val > 0 else 0
            name = NUTRIENT_NAMES.get(nutrient, nutrient)

            status_info = {
                "nutrient": nutrient,
                "name": name,
                "current": round(current, 1),
                "target": target_val,
                "percentage": round(pct, 1),
                "unit": self._get_unit(nutrient),
            }

            if nutrient in MAX_NUTRIENTS:
                # For max-limit nutrients, exceeding is bad
                if pct > 100:
                    status_info["status"] = "excess"
                    status_info["message"] = f"{name} is {round(pct - 100)}% over the recommended maximum"
                    analysis["excesses"].append(status_info)
                else:
                    status_info["status"] = "good"
                    analysis["on_track"].append(status_info)
            else:
                # For other nutrients, being under is a deficiency
                if pct < 50:
                    status_info["status"] = "deficient"
                    status_info["message"] = f"{name} is significantly low at {round(pct)}% of target"
                    status_info["food_sources"] = FOOD_SOURCES.get(nutrient, [])
                    analysis["deficiencies"].append(status_info)
                elif pct < 80:
                    status_info["status"] = "low"
                    status_info["message"] = f"{name} is below target at {round(pct)}%"
                    status_info["food_sources"] = FOOD_SOURCES.get(nutrient, [])
                    analysis["deficiencies"].append(status_info)
                elif pct <= 150:
                    status_info["status"] = "good"
                    analysis["on_track"].append(status_info)
                else:
                    status_info["status"] = "high"
                    status_info["message"] = f"{name} is {round(pct)}% of target - may be excessive"
                    analysis["excesses"].append(status_info)

            analysis["nutrients"][nutrient] = status_info

        # Generate overall score
        total = len(rda)
        good = len(analysis["on_track"])
        analysis["score"] = round(good / total * 100) if total > 0 else 0
        analysis["summary"] = self._generate_summary(analysis)

        return analysis

    def analyze_weekly(self, user_id, weeks=1):
        """Analyze nutrient intake over a week, detecting persistent deficiencies."""
        end = date.today()
        start = end - timedelta(days=7 * weeks)
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        rda = self.get_rda(user)
        days_analyzed = 0
        weekly_intake = {key: 0 for key in rda}

        current = start
        while current <= end:
            entries = FoodEntry.query.filter_by(
                user_id=user_id, date=current
            ).all()
            if entries:
                days_analyzed += 1
                for key in rda:
                    weekly_intake[key] += sum(
                        getattr(e, key, 0) or 0 for e in entries
                    )
            current += timedelta(days=1)

        if days_analyzed == 0:
            return {"message": "No food data found for this period"}

        # Average daily intake
        avg_intake = {k: v / days_analyzed for k, v in weekly_intake.items()}

        persistent_deficiencies = []
        persistent_excesses = []

        for nutrient, target_val in rda.items():
            if target_val == 0:
                continue
            avg = avg_intake.get(nutrient, 0)
            pct = (avg / target_val * 100) if target_val > 0 else 0
            name = NUTRIENT_NAMES.get(nutrient, nutrient)

            if nutrient not in MAX_NUTRIENTS and pct < 80:
                persistent_deficiencies.append({
                    "nutrient": nutrient, "name": name,
                    "avg_daily": round(avg, 1), "target": target_val,
                    "percentage": round(pct, 1),
                    "food_sources": FOOD_SOURCES.get(nutrient, []),
                    "health_impact": self._get_deficiency_impact(nutrient),
                })
            elif nutrient in MAX_NUTRIENTS and pct > 120:
                persistent_excesses.append({
                    "nutrient": nutrient, "name": name,
                    "avg_daily": round(avg, 1), "target": target_val,
                    "percentage": round(pct, 1),
                })

        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "days_analyzed": days_analyzed,
            "avg_daily_intake": {k: round(v, 1) for k, v in avg_intake.items()},
            "persistent_deficiencies": persistent_deficiencies,
            "persistent_excesses": persistent_excesses,
        }

    def _get_unit(self, nutrient):
        if nutrient == "calories":
            return "kcal"
        if "mcg" in nutrient:
            return "mcg"
        if "mg" in nutrient:
            return "mg"
        if "ml" in nutrient:
            return "ml"
        if "_g" in nutrient:
            return "g"
        return ""

    def _get_deficiency_impact(self, nutrient):
        """Return health impact descriptions for nutrient deficiencies."""
        impacts = {
            "protein_g": "Muscle loss, weakened immunity, slow recovery",
            "iron_mg": "Fatigue, weakness, poor concentration, anemia",
            "calcium_mg": "Weak bones, muscle cramps, dental problems",
            "vitamin_d_mcg": "Bone weakness, fatigue, mood changes, weakened immunity",
            "vitamin_b12_mcg": "Fatigue, nerve damage, anemia, cognitive issues",
            "magnesium_mg": "Muscle cramps, poor sleep, anxiety, fatigue",
            "zinc_mg": "Weakened immunity, slow wound healing, hair loss",
            "potassium_mg": "Muscle weakness, fatigue, irregular heartbeat",
            "vitamin_c_mg": "Weakened immunity, slow wound healing, fatigue",
            "folate_mcg": "Fatigue, mouth sores, growth issues",
            "fiber_g": "Digestive issues, blood sugar spikes, increased hunger",
            "vitamin_a_mcg": "Poor night vision, weakened immunity, skin issues",
            "vitamin_k_mcg": "Easy bruising, excessive bleeding",
            "vitamin_e_mg": "Nerve damage, weakened immunity, vision problems",
            "water_ml": "Dehydration, headaches, fatigue, poor performance",
        }
        return impacts.get(nutrient, "May affect overall health")

    def _generate_summary(self, analysis):
        """Generate a human-readable summary of the analysis."""
        deficiencies = analysis["deficiencies"]
        excesses = analysis["excesses"]
        score = analysis["score"]

        parts = []

        if score >= 90:
            parts.append("Excellent nutrition today! You're hitting most of your targets.")
        elif score >= 70:
            parts.append("Good nutrition overall, with a few areas to improve.")
        elif score >= 50:
            parts.append("Your nutrition needs attention in several areas.")
        else:
            parts.append("Significant nutritional gaps detected today.")

        if deficiencies:
            critical = [d for d in deficiencies if d["status"] == "deficient"]
            if critical:
                names = [d["name"] for d in critical[:3]]
                parts.append(f"Critical gaps: {', '.join(names)}.")

        if excesses:
            names = [e["name"] for e in excesses[:2]]
            parts.append(f"Consider reducing: {', '.join(names)}.")

        return " ".join(parts)
