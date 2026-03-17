"""Food and drink tracking service with image analysis and macro calculation."""

import json
import os
from datetime import date, datetime
from models.database import db, FoodEntry

# Comprehensive food database with full nutrient profiles
FOOD_DATABASE = {
    # Proteins
    "chicken breast": {
        "serving_size": "100g", "calories": 165, "protein_g": 31, "carbs_g": 0,
        "fat_g": 3.6, "fiber_g": 0, "sugar_g": 0, "saturated_fat_g": 1,
        "sodium_mg": 74, "potassium_mg": 256, "calcium_mg": 15, "iron_mg": 1,
        "magnesium_mg": 29, "zinc_mg": 1, "phosphorus_mg": 228,
        "vitamin_b3_mg": 13.7, "vitamin_b6_mg": 0.6, "vitamin_b12_mcg": 0.3,
    },
    "salmon": {
        "serving_size": "100g", "calories": 208, "protein_g": 20, "carbs_g": 0,
        "fat_g": 13, "fiber_g": 0, "sugar_g": 0, "saturated_fat_g": 3.1,
        "sodium_mg": 59, "potassium_mg": 363, "calcium_mg": 12, "iron_mg": 0.8,
        "magnesium_mg": 29, "zinc_mg": 0.6, "phosphorus_mg": 240,
        "vitamin_b12_mcg": 3.2, "vitamin_d_mcg": 11, "vitamin_b6_mg": 0.6,
    },
    "eggs": {
        "serving_size": "1 large (50g)", "calories": 72, "protein_g": 6.3,
        "carbs_g": 0.4, "fat_g": 5, "fiber_g": 0, "sugar_g": 0.2,
        "saturated_fat_g": 1.6, "sodium_mg": 71, "potassium_mg": 69,
        "calcium_mg": 28, "iron_mg": 0.9, "magnesium_mg": 6, "zinc_mg": 0.6,
        "vitamin_a_mcg": 80, "vitamin_b12_mcg": 0.4, "vitamin_d_mcg": 1,
        "folate_mcg": 24, "phosphorus_mg": 99,
    },
    "greek yogurt": {
        "serving_size": "170g", "calories": 100, "protein_g": 17, "carbs_g": 6,
        "fat_g": 0.7, "fiber_g": 0, "sugar_g": 6, "saturated_fat_g": 0.3,
        "calcium_mg": 187, "potassium_mg": 240, "sodium_mg": 68,
        "vitamin_b12_mcg": 1.3, "phosphorus_mg": 230,
    },
    "tofu": {
        "serving_size": "100g", "calories": 76, "protein_g": 8, "carbs_g": 1.9,
        "fat_g": 4.8, "fiber_g": 0.3, "calcium_mg": 350, "iron_mg": 5.4,
        "magnesium_mg": 30, "zinc_mg": 0.8, "phosphorus_mg": 97,
    },

    # Carbs
    "brown rice": {
        "serving_size": "100g cooked", "calories": 123, "protein_g": 2.7,
        "carbs_g": 26, "fat_g": 1, "fiber_g": 1.8, "sugar_g": 0.4,
        "magnesium_mg": 39, "phosphorus_mg": 103, "potassium_mg": 86,
        "iron_mg": 0.6, "zinc_mg": 0.6, "vitamin_b3_mg": 2.6,
    },
    "sweet potato": {
        "serving_size": "100g", "calories": 86, "protein_g": 1.6, "carbs_g": 20,
        "fat_g": 0.1, "fiber_g": 3, "sugar_g": 4.2, "vitamin_a_mcg": 709,
        "vitamin_c_mg": 2.4, "potassium_mg": 337, "magnesium_mg": 25,
        "calcium_mg": 30, "iron_mg": 0.6,
    },
    "oatmeal": {
        "serving_size": "100g cooked", "calories": 71, "protein_g": 2.5,
        "carbs_g": 12, "fat_g": 1.5, "fiber_g": 1.7, "sugar_g": 0.3,
        "iron_mg": 1.4, "magnesium_mg": 27, "phosphorus_mg": 77,
        "zinc_mg": 0.6, "vitamin_b1_mg": 0.1,
    },
    "quinoa": {
        "serving_size": "100g cooked", "calories": 120, "protein_g": 4.4,
        "carbs_g": 21, "fat_g": 1.9, "fiber_g": 2.8, "iron_mg": 1.5,
        "magnesium_mg": 64, "phosphorus_mg": 152, "zinc_mg": 1.1,
        "folate_mcg": 42, "vitamin_b6_mg": 0.1,
    },

    # Vegetables
    "broccoli": {
        "serving_size": "100g", "calories": 34, "protein_g": 2.8, "carbs_g": 7,
        "fat_g": 0.4, "fiber_g": 2.6, "vitamin_c_mg": 89, "vitamin_k_mcg": 102,
        "folate_mcg": 63, "vitamin_a_mcg": 31, "calcium_mg": 47,
        "potassium_mg": 316, "iron_mg": 0.7, "magnesium_mg": 21,
    },
    "spinach": {
        "serving_size": "100g", "calories": 23, "protein_g": 2.9, "carbs_g": 3.6,
        "fat_g": 0.4, "fiber_g": 2.2, "vitamin_a_mcg": 469, "vitamin_c_mg": 28,
        "vitamin_k_mcg": 483, "folate_mcg": 194, "iron_mg": 2.7,
        "calcium_mg": 99, "magnesium_mg": 79, "potassium_mg": 558,
    },
    "avocado": {
        "serving_size": "100g", "calories": 160, "protein_g": 2, "carbs_g": 9,
        "fat_g": 15, "fiber_g": 7, "vitamin_k_mcg": 21, "folate_mcg": 81,
        "vitamin_c_mg": 10, "vitamin_e_mg": 2.1, "potassium_mg": 485,
        "magnesium_mg": 29,
    },

    # Fruits
    "banana": {
        "serving_size": "1 medium (118g)", "calories": 105, "protein_g": 1.3,
        "carbs_g": 27, "fat_g": 0.4, "fiber_g": 3.1, "sugar_g": 14,
        "potassium_mg": 422, "vitamin_b6_mg": 0.4, "vitamin_c_mg": 10,
        "magnesium_mg": 32, "folate_mcg": 24,
    },
    "blueberries": {
        "serving_size": "100g", "calories": 57, "protein_g": 0.7, "carbs_g": 14,
        "fat_g": 0.3, "fiber_g": 2.4, "sugar_g": 10, "vitamin_c_mg": 10,
        "vitamin_k_mcg": 19, "vitamin_e_mg": 0.6,
    },

    # Fats
    "almonds": {
        "serving_size": "28g (1 oz)", "calories": 164, "protein_g": 6,
        "carbs_g": 6, "fat_g": 14, "fiber_g": 3.5, "vitamin_e_mg": 7.3,
        "magnesium_mg": 76, "calcium_mg": 76, "iron_mg": 1, "zinc_mg": 0.9,
        "phosphorus_mg": 137,
    },
    "olive oil": {
        "serving_size": "1 tbsp (14g)", "calories": 119, "protein_g": 0,
        "carbs_g": 0, "fat_g": 14, "saturated_fat_g": 1.9,
        "vitamin_e_mg": 1.9, "vitamin_k_mcg": 8.1,
    },

    # Drinks
    "gin and soda": {
        "serving_size": "1 drink", "calories": 97, "protein_g": 0,
        "carbs_g": 0, "fat_g": 0, "sugar_g": 0, "is_alcoholic": True,
        "alcohol_units": 1.0, "water_ml": 150,
    },
    "gin and tonic": {
        "serving_size": "1 drink", "calories": 171, "protein_g": 0,
        "carbs_g": 16, "fat_g": 0, "sugar_g": 16, "is_alcoholic": True,
        "alcohol_units": 1.0, "water_ml": 150,
    },
    "red wine": {
        "serving_size": "150ml", "calories": 125, "protein_g": 0.1,
        "carbs_g": 3.8, "fat_g": 0, "is_alcoholic": True,
        "alcohol_units": 1.5, "iron_mg": 0.5, "potassium_mg": 127,
    },
    "beer": {
        "serving_size": "330ml", "calories": 153, "protein_g": 1.6,
        "carbs_g": 13, "fat_g": 0, "is_alcoholic": True,
        "alcohol_units": 1.3, "water_ml": 300,
    },
    "black coffee": {
        "serving_size": "240ml", "calories": 2, "protein_g": 0.3,
        "carbs_g": 0, "fat_g": 0, "caffeine_mg": 95, "water_ml": 240,
        "potassium_mg": 116, "magnesium_mg": 7,
    },
    "green tea": {
        "serving_size": "240ml", "calories": 2, "protein_g": 0,
        "carbs_g": 0, "fat_g": 0, "caffeine_mg": 28, "water_ml": 240,
    },
    "water": {
        "serving_size": "250ml", "calories": 0, "protein_g": 0,
        "carbs_g": 0, "fat_g": 0, "water_ml": 250,
    },
    "protein shake": {
        "serving_size": "1 scoop (30g) + water", "calories": 120,
        "protein_g": 25, "carbs_g": 3, "fat_g": 1.5, "fiber_g": 0,
        "calcium_mg": 100, "iron_mg": 2, "water_ml": 300,
    },
}


class FoodService:
    """Service for tracking food/drink intake and analyzing nutrition."""

    def __init__(self):
        self.food_db = FOOD_DATABASE

    def search_food(self, query):
        """Search the food database by name."""
        query_lower = query.lower().strip()
        results = []
        for name, data in self.food_db.items():
            if query_lower in name.lower():
                results.append({"name": name, **data})
        return results

    def log_food(self, user_id, name, meal_type, servings=1.0,
                 image_path=None, custom_nutrients=None):
        """Log a food or drink entry."""
        # Look up in database or use custom nutrients
        nutrients = self.food_db.get(name.lower(), {})
        if custom_nutrients:
            nutrients.update(custom_nutrients)

        entry = FoodEntry(
            user_id=user_id,
            name=name,
            meal_type=meal_type,
            servings=servings,
            serving_size=nutrients.get("serving_size", "1 serving"),
            image_path=image_path,
            calories=nutrients.get("calories", 0) * servings,
            protein_g=nutrients.get("protein_g", 0) * servings,
            carbs_g=nutrients.get("carbs_g", 0) * servings,
            fat_g=nutrients.get("fat_g", 0) * servings,
            fiber_g=nutrients.get("fiber_g", 0) * servings,
            sugar_g=nutrients.get("sugar_g", 0) * servings,
            saturated_fat_g=nutrients.get("saturated_fat_g", 0) * servings,
            sodium_mg=nutrients.get("sodium_mg", 0) * servings,
            potassium_mg=nutrients.get("potassium_mg", 0) * servings,
            calcium_mg=nutrients.get("calcium_mg", 0) * servings,
            iron_mg=nutrients.get("iron_mg", 0) * servings,
            magnesium_mg=nutrients.get("magnesium_mg", 0) * servings,
            zinc_mg=nutrients.get("zinc_mg", 0) * servings,
            phosphorus_mg=nutrients.get("phosphorus_mg", 0) * servings,
            vitamin_a_mcg=nutrients.get("vitamin_a_mcg", 0) * servings,
            vitamin_b1_mg=nutrients.get("vitamin_b1_mg", 0) * servings,
            vitamin_b2_mg=nutrients.get("vitamin_b2_mg", 0) * servings,
            vitamin_b3_mg=nutrients.get("vitamin_b3_mg", 0) * servings,
            vitamin_b6_mg=nutrients.get("vitamin_b6_mg", 0) * servings,
            vitamin_b12_mcg=nutrients.get("vitamin_b12_mcg", 0) * servings,
            vitamin_c_mg=nutrients.get("vitamin_c_mg", 0) * servings,
            vitamin_d_mcg=nutrients.get("vitamin_d_mcg", 0) * servings,
            vitamin_e_mg=nutrients.get("vitamin_e_mg", 0) * servings,
            vitamin_k_mcg=nutrients.get("vitamin_k_mcg", 0) * servings,
            folate_mcg=nutrients.get("folate_mcg", 0) * servings,
            is_alcoholic=nutrients.get("is_alcoholic", False),
            alcohol_units=nutrients.get("alcohol_units", 0) * servings,
            water_ml=nutrients.get("water_ml", 0) * servings,
            caffeine_mg=nutrients.get("caffeine_mg", 0) * servings,
        )

        db.session.add(entry)
        db.session.commit()
        return entry

    def log_custom_food(self, user_id, name, meal_type, nutrients, servings=1.0,
                        image_path=None):
        """Log a custom food entry with manually specified nutrients."""
        return self.log_food(user_id, name, meal_type, servings,
                             image_path, nutrients)

    def get_daily_summary(self, user_id, target_date=None):
        """Get nutritional summary for a specific day."""
        target = target_date or date.today()
        entries = FoodEntry.query.filter_by(
            user_id=user_id, date=target
        ).all()

        summary = {
            "date": target.isoformat(),
            "entries": [e.to_dict() for e in entries],
            "totals": self._calculate_totals(entries),
            "meals": {},
        }

        # Group by meal type
        for entry in entries:
            meal = entry.meal_type or "other"
            if meal not in summary["meals"]:
                summary["meals"][meal] = {"entries": [], "totals": {}}
            summary["meals"][meal]["entries"].append(entry.to_dict())

        for meal, data in summary["meals"].items():
            meal_entries = FoodEntry.query.filter_by(
                user_id=user_id, date=target, meal_type=meal
            ).all()
            data["totals"] = self._calculate_totals(meal_entries)

        return summary

    def _calculate_totals(self, entries):
        """Sum up all nutrients from a list of food entries."""
        totals = {
            "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
            "fiber_g": 0, "sugar_g": 0, "saturated_fat_g": 0,
            "sodium_mg": 0, "potassium_mg": 0, "calcium_mg": 0,
            "iron_mg": 0, "magnesium_mg": 0, "zinc_mg": 0,
            "phosphorus_mg": 0, "vitamin_a_mcg": 0, "vitamin_b1_mg": 0,
            "vitamin_b2_mg": 0, "vitamin_b3_mg": 0, "vitamin_b6_mg": 0,
            "vitamin_b12_mcg": 0, "vitamin_c_mg": 0, "vitamin_d_mcg": 0,
            "vitamin_e_mg": 0, "vitamin_k_mcg": 0, "folate_mcg": 0,
            "alcohol_units": 0, "water_ml": 0, "caffeine_mg": 0,
        }

        for entry in entries:
            for key in totals:
                totals[key] += getattr(entry, key, 0) or 0

        return totals

    def analyze_image(self, image_path):
        """Analyze a food image and estimate nutrients.

        In production, this would call a vision AI API (e.g., Claude Vision,
        Google Vision) to identify food items and estimate portions.
        Returns estimated nutrient data.
        """
        # Placeholder - in production, integrate with a vision API
        return {
            "identified_items": [
                {"name": "Unable to analyze - please enter food details manually",
                 "confidence": 0}
            ],
            "message": (
                "Image analysis requires a vision AI API key. "
                "Please configure VISION_API_KEY in your .env file, "
                "or enter food details manually."
            ),
        }

    def get_weekly_trend(self, user_id, weeks=1):
        """Get nutritional trends for the past N weeks."""
        from datetime import timedelta
        end = date.today()
        start = end - timedelta(weeks=weeks * 7)

        entries = FoodEntry.query.filter(
            FoodEntry.user_id == user_id,
            FoodEntry.date >= start,
            FoodEntry.date <= end,
        ).all()

        daily = {}
        for entry in entries:
            d = entry.date.isoformat()
            if d not in daily:
                daily[d] = []
            daily[d].append(entry)

        trend = []
        for d, day_entries in sorted(daily.items()):
            totals = self._calculate_totals(day_entries)
            totals["date"] = d
            trend.append(totals)

        return trend
