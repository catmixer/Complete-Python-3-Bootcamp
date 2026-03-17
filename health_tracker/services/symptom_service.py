"""Symptom tracking and health correlation analysis service."""

import json
from datetime import date, timedelta
from models.database import db, User, SymptomEntry, FoodEntry, FitnessData, BodyMetric


# Known correlations between symptoms and nutrient deficiencies / lifestyle factors
SYMPTOM_CORRELATIONS = {
    "headache": {
        "nutrient_triggers": {
            "water_ml": {"threshold": "low", "message": "Dehydration is a leading cause of headaches"},
            "magnesium_mg": {"threshold": "low", "message": "Low magnesium can trigger headaches"},
            "caffeine_mg": {"threshold": "high", "message": "Excess caffeine can cause headaches"},
            "sodium_mg": {"threshold": "high", "message": "High sodium can elevate blood pressure causing headaches"},
        },
        "fitness_triggers": {
            "sleep_hours": {"threshold": "low", "min": 6, "message": "Poor sleep is a common headache trigger"},
        },
        "recommendations": [
            "Drink at least 2-3 liters of water today",
            "Take magnesium supplement (400mg)",
            "Reduce caffeine intake",
            "Ensure 7-8 hours of sleep tonight",
            "Try a cool compress on your forehead",
        ],
    },
    "fatigue": {
        "nutrient_triggers": {
            "iron_mg": {"threshold": "low", "message": "Iron deficiency causes fatigue and weakness"},
            "vitamin_b12_mcg": {"threshold": "low", "message": "B12 deficiency leads to fatigue"},
            "vitamin_d_mcg": {"threshold": "low", "message": "Low vitamin D is linked to fatigue"},
            "calories": {"threshold": "low", "message": "Insufficient calorie intake causes energy depletion"},
            "water_ml": {"threshold": "low", "message": "Dehydration contributes to fatigue"},
        },
        "fitness_triggers": {
            "sleep_hours": {"threshold": "low", "min": 7, "message": "Insufficient sleep directly causes fatigue"},
            "recovery_score": {"threshold": "low", "min": 33, "message": "Low recovery score indicates physical exhaustion"},
            "strain_score": {"threshold": "high", "max": 18, "message": "Excessive strain may be causing burnout"},
        },
        "recommendations": [
            "Check iron and B12 levels with blood work",
            "Eat iron-rich foods (spinach, red meat, lentils)",
            "Get 20 minutes of sunlight for vitamin D",
            "Prioritize 8 hours of sleep",
            "Consider a rest day if recovery is low",
            "Stay hydrated throughout the day",
        ],
    },
    "muscle_cramps": {
        "nutrient_triggers": {
            "magnesium_mg": {"threshold": "low", "message": "Magnesium deficiency causes muscle cramps"},
            "potassium_mg": {"threshold": "low", "message": "Low potassium leads to muscle cramps"},
            "calcium_mg": {"threshold": "low", "message": "Calcium deficiency can cause muscle spasms"},
            "water_ml": {"threshold": "low", "message": "Dehydration triggers muscle cramps"},
            "sodium_mg": {"threshold": "low", "message": "Low sodium after heavy sweating causes cramps"},
        },
        "fitness_triggers": {
            "strain_score": {"threshold": "high", "max": 16, "message": "High physical strain contributes to cramping"},
        },
        "recommendations": [
            "Eat a banana (potassium) and almonds (magnesium)",
            "Drink electrolyte water",
            "Stretch and foam roll affected muscles",
            "Take a warm bath with Epsom salts",
            "Consider magnesium supplement before bed",
        ],
    },
    "bloating": {
        "nutrient_triggers": {
            "fiber_g": {"threshold": "high", "message": "Sudden increase in fiber can cause bloating"},
            "sodium_mg": {"threshold": "high", "message": "High sodium causes water retention and bloating"},
            "water_ml": {"threshold": "low", "message": "Low water intake worsens bloating"},
        },
        "food_triggers": ["dairy", "beans", "carbonated drinks", "artificial sweeteners", "wheat"],
        "recommendations": [
            "Drink peppermint or ginger tea",
            "Go for a 15-minute walk",
            "Avoid carbonated beverages",
            "Eat slowly and chew thoroughly",
            "Gradually increase fiber intake rather than suddenly",
        ],
    },
    "insomnia": {
        "nutrient_triggers": {
            "caffeine_mg": {"threshold": "high", "message": "Excess caffeine disrupts sleep"},
            "magnesium_mg": {"threshold": "low", "message": "Low magnesium affects sleep quality"},
            "sugar_g": {"threshold": "high", "message": "High sugar intake can disrupt sleep patterns"},
        },
        "fitness_triggers": {
            "strain_score": {"threshold": "high", "max": 18, "message": "Very high strain may cause restlessness"},
        },
        "recommendations": [
            "No caffeine after 2 PM",
            "Take magnesium before bed",
            "Avoid screens 1 hour before sleep",
            "Try chamomile tea in the evening",
            "Keep bedroom cool and dark",
            "No intense exercise within 3 hours of bedtime",
        ],
    },
    "skin_issue": {
        "nutrient_triggers": {
            "water_ml": {"threshold": "low", "message": "Dehydration affects skin health"},
            "vitamin_a_mcg": {"threshold": "low", "message": "Vitamin A deficiency causes skin problems"},
            "vitamin_c_mg": {"threshold": "low", "message": "Vitamin C is essential for skin repair"},
            "zinc_mg": {"threshold": "low", "message": "Zinc deficiency linked to skin inflammation"},
            "vitamin_e_mg": {"threshold": "low", "message": "Vitamin E protects skin from damage"},
            "sugar_g": {"threshold": "high", "message": "High sugar intake worsens skin conditions"},
        },
        "recommendations": [
            "Increase water intake to 3+ liters",
            "Eat foods rich in vitamins A, C, and E",
            "Reduce sugar and processed food intake",
            "Consider zinc supplement",
            "Track if specific foods correlate with flare-ups",
        ],
    },
    "nausea": {
        "nutrient_triggers": {
            "fat_g": {"threshold": "high", "message": "Very high fat intake can cause nausea"},
            "sugar_g": {"threshold": "high", "message": "Excess sugar can trigger nausea"},
        },
        "fitness_triggers": {
            "strain_score": {"threshold": "high", "max": 18, "message": "Extreme exertion can cause nausea"},
        },
        "recommendations": [
            "Eat small, bland meals (crackers, rice, bananas)",
            "Sip ginger tea or flat ginger ale",
            "Avoid heavy, greasy foods",
            "Stay hydrated with small sips",
            "Rest in an upright position",
        ],
    },
    "brain_fog": {
        "nutrient_triggers": {
            "vitamin_b12_mcg": {"threshold": "low", "message": "B12 deficiency impairs cognitive function"},
            "iron_mg": {"threshold": "low", "message": "Iron deficiency reduces oxygen to the brain"},
            "water_ml": {"threshold": "low", "message": "Dehydration impairs concentration"},
            "carbs_g": {"threshold": "low", "message": "Very low carbs can cause brain fog"},
        },
        "fitness_triggers": {
            "sleep_hours": {"threshold": "low", "min": 7, "message": "Poor sleep directly causes brain fog"},
        },
        "recommendations": [
            "Eat complex carbs for steady energy",
            "Check B12 and iron levels",
            "Stay well hydrated",
            "Take breaks from screens",
            "Try a brief walk for mental clarity",
        ],
    },
    "joint_pain": {
        "nutrient_triggers": {
            "vitamin_d_mcg": {"threshold": "low", "message": "Vitamin D deficiency linked to joint pain"},
            "calcium_mg": {"threshold": "low", "message": "Low calcium affects bone and joint health"},
        },
        "fitness_triggers": {
            "strain_score": {"threshold": "high", "max": 16, "message": "High strain may aggravate joints"},
        },
        "recommendations": [
            "Anti-inflammatory foods: fatty fish, turmeric, ginger",
            "Ensure adequate vitamin D and calcium intake",
            "Apply ice to affected joints",
            "Low-impact exercise (swimming, cycling)",
            "Consider omega-3 supplement",
        ],
    },
    "anxiety": {
        "nutrient_triggers": {
            "magnesium_mg": {"threshold": "low", "message": "Magnesium deficiency linked to anxiety"},
            "vitamin_b6_mg": {"threshold": "low", "message": "B6 helps produce calming neurotransmitters"},
            "caffeine_mg": {"threshold": "high", "message": "Excess caffeine can worsen anxiety"},
        },
        "fitness_triggers": {
            "sleep_hours": {"threshold": "low", "min": 7, "message": "Poor sleep exacerbates anxiety"},
        },
        "recommendations": [
            "Reduce caffeine intake immediately",
            "Magnesium-rich foods: dark chocolate, almonds, spinach",
            "Practice deep breathing or meditation",
            "Go for a walk in nature",
            "Prioritize sleep tonight",
        ],
    },
}


class SymptomService:
    """Tracks symptoms and correlates them with nutrition, fitness, and lifestyle data."""

    def log_symptom(self, user_id, symptom_type, description=None,
                    severity=5, image_path=None, body_area=None,
                    duration_hours=None):
        """Log a symptom and run correlation analysis."""
        entry = SymptomEntry(
            user_id=user_id,
            symptom_type=symptom_type,
            description=description,
            severity=severity,
            image_path=image_path,
            body_area=body_area,
            duration_hours=duration_hours,
        )

        # Run correlation analysis
        analysis = self.analyze_symptom(user_id, symptom_type, severity)
        entry.ai_analysis = analysis.get("analysis", "")
        entry.correlations = json.dumps(analysis.get("correlations", []))
        entry.recommendations = json.dumps(analysis.get("recommendations", []))

        db.session.add(entry)
        db.session.commit()

        return {
            "symptom": entry.to_dict(),
            "analysis": analysis,
        }

    def analyze_symptom(self, user_id, symptom_type, severity=5):
        """Analyze a symptom against recent nutrition and fitness data."""
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        correlations = []
        recommendations = []
        analysis_parts = []

        # Get recent nutrition data (last 3 days)
        recent_nutrition = self._get_recent_nutrition(user_id, days=3)

        # Get recent fitness data
        recent_fitness = self._get_recent_fitness(user_id, days=3)

        # Check known correlations
        known = SYMPTOM_CORRELATIONS.get(symptom_type, {})

        # Check nutrient triggers
        nutrient_triggers = known.get("nutrient_triggers", {})
        for nutrient, trigger in nutrient_triggers.items():
            avg = recent_nutrition.get(nutrient, 0)
            rda = self._get_rda(user, nutrient)

            if trigger["threshold"] == "low" and rda > 0 and avg < rda * 0.6:
                pct = round(avg / rda * 100)
                correlations.append({
                    "type": "nutrient_deficiency",
                    "nutrient": nutrient,
                    "current_avg": round(avg, 1),
                    "recommended": rda,
                    "percentage": pct,
                    "message": trigger["message"],
                    "confidence": "high" if avg < rda * 0.4 else "medium",
                })
                analysis_parts.append(
                    f"Your {nutrient.replace('_', ' ')} intake has been low "
                    f"({pct}% of recommended). {trigger['message']}."
                )
            elif trigger["threshold"] == "high" and avg > rda * 1.5:
                correlations.append({
                    "type": "nutrient_excess",
                    "nutrient": nutrient,
                    "current_avg": round(avg, 1),
                    "recommended": rda,
                    "message": trigger["message"],
                    "confidence": "medium",
                })
                analysis_parts.append(
                    f"Your {nutrient.replace('_', ' ')} intake has been high. "
                    f"{trigger['message']}."
                )

        # Check fitness triggers
        fitness_triggers = known.get("fitness_triggers", {})
        for metric, trigger in fitness_triggers.items():
            value = recent_fitness.get(metric)
            if value is None:
                continue

            if trigger["threshold"] == "low" and value < trigger.get("min", 0):
                correlations.append({
                    "type": "fitness_factor",
                    "metric": metric,
                    "current": round(value, 1),
                    "threshold": trigger.get("min"),
                    "message": trigger["message"],
                    "confidence": "high",
                })
                analysis_parts.append(
                    f"Your {metric.replace('_', ' ')} ({round(value, 1)}) is below "
                    f"optimal. {trigger['message']}."
                )
            elif trigger["threshold"] == "high" and value > trigger.get("max", 999):
                correlations.append({
                    "type": "fitness_factor",
                    "metric": metric,
                    "current": round(value, 1),
                    "threshold": trigger.get("max"),
                    "message": trigger["message"],
                    "confidence": "medium",
                })

        # Check food-specific triggers
        food_triggers = known.get("food_triggers", [])
        if food_triggers:
            recent_foods = self._get_recent_food_names(user_id, days=2)
            flagged_foods = [f for f in food_triggers if any(
                f.lower() in food.lower() for food in recent_foods
            )]
            if flagged_foods:
                correlations.append({
                    "type": "food_trigger",
                    "foods": flagged_foods,
                    "message": f"Recent consumption of {', '.join(flagged_foods)} may be a trigger",
                    "confidence": "medium",
                })

        # Add known recommendations
        recommendations = list(known.get("recommendations", []))

        # Add severity-based advice
        if severity >= 7:
            analysis_parts.append(
                "Given the high severity, consider consulting a healthcare provider "
                "if symptoms persist for more than 24-48 hours."
            )
            recommendations.insert(0, "Consider seeing a doctor if this persists")

        # Check for recurring patterns
        pattern = self._check_recurring_pattern(user_id, symptom_type)
        if pattern:
            correlations.append(pattern)
            analysis_parts.append(
                f"This symptom has occurred {pattern['occurrences']} times "
                f"in the past {pattern['period_days']} days, suggesting a pattern."
            )

        analysis_text = " ".join(analysis_parts) if analysis_parts else (
            f"Logged {symptom_type} with severity {severity}/10. "
            "Continue tracking to identify patterns."
        )

        return {
            "analysis": analysis_text,
            "correlations": correlations,
            "recommendations": recommendations,
            "severity_level": (
                "mild" if severity <= 3
                else "moderate" if severity <= 6
                else "severe"
            ),
        }

    def _get_recent_nutrition(self, user_id, days=3):
        """Get average daily nutrition for the past N days."""
        end = date.today()
        start = end - timedelta(days=days)

        entries = FoodEntry.query.filter(
            FoodEntry.user_id == user_id,
            FoodEntry.date >= start,
            FoodEntry.date <= end,
        ).all()

        if not entries:
            return {}

        # Count unique days with entries
        unique_days = len(set(e.date for e in entries))
        if unique_days == 0:
            return {}

        nutrient_fields = [
            "calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g",
            "sodium_mg", "potassium_mg", "calcium_mg", "iron_mg", "magnesium_mg",
            "zinc_mg", "vitamin_a_mcg", "vitamin_b6_mg", "vitamin_b12_mcg",
            "vitamin_c_mg", "vitamin_d_mcg", "vitamin_e_mg", "vitamin_k_mcg",
            "folate_mcg", "water_ml", "caffeine_mg", "saturated_fat_g",
        ]

        totals = {}
        for field in nutrient_fields:
            totals[field] = sum(getattr(e, field, 0) or 0 for e in entries) / unique_days

        return totals

    def _get_recent_fitness(self, user_id, days=3):
        """Get average fitness metrics for the past N days."""
        end = date.today()
        start = end - timedelta(days=days)

        records = FitnessData.query.filter(
            FitnessData.user_id == user_id,
            FitnessData.date >= start,
            FitnessData.date <= end,
        ).all()

        if not records:
            return {}

        metrics = {}
        for field in ["sleep_hours", "recovery_score", "strain_score",
                       "resting_heart_rate", "hrv_ms", "exercise_minutes"]:
            values = [getattr(r, field) for r in records if getattr(r, field) is not None]
            if values:
                metrics[field] = sum(values) / len(values)

        return metrics

    def _get_recent_food_names(self, user_id, days=2):
        """Get list of food names consumed recently."""
        end = date.today()
        start = end - timedelta(days=days)
        entries = FoodEntry.query.filter(
            FoodEntry.user_id == user_id,
            FoodEntry.date >= start,
        ).all()
        return [e.name for e in entries]

    def _get_rda(self, user, nutrient):
        """Get recommended daily allowance for a nutrient."""
        from services.nutrient_service import RDA
        gender = user.gender or "male"
        return RDA.get(gender, RDA["male"]).get(nutrient, 0)

    def _check_recurring_pattern(self, user_id, symptom_type, days=30):
        """Check if a symptom has been recurring."""
        end = date.today()
        start = end - timedelta(days=days)

        count = SymptomEntry.query.filter(
            SymptomEntry.user_id == user_id,
            SymptomEntry.symptom_type == symptom_type,
            SymptomEntry.date >= start,
        ).count()

        if count >= 3:
            return {
                "type": "recurring_pattern",
                "symptom_type": symptom_type,
                "occurrences": count,
                "period_days": days,
                "message": f"Recurring {symptom_type} detected ({count} times in {days} days). "
                           f"Consider seeing a healthcare professional.",
                "confidence": "high",
            }
        return None

    def get_symptom_history(self, user_id, days=30):
        """Get symptom history with analysis."""
        end = date.today()
        start = end - timedelta(days=days)

        entries = SymptomEntry.query.filter(
            SymptomEntry.user_id == user_id,
            SymptomEntry.date >= start,
        ).order_by(SymptomEntry.timestamp.desc()).all()

        # Count symptom types
        type_counts = {}
        for e in entries:
            t = e.symptom_type
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "entries": [e.to_dict() for e in entries],
            "total_count": len(entries),
            "type_counts": type_counts,
            "most_common": max(type_counts, key=type_counts.get) if type_counts else None,
        }

    def resolve_symptom(self, symptom_id):
        """Mark a symptom as resolved."""
        from datetime import datetime
        entry = SymptomEntry.query.get(symptom_id)
        if entry:
            entry.resolved = True
            entry.resolved_at = datetime.utcnow()
            db.session.commit()
        return entry
