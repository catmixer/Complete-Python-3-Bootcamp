"""Apple Health data client.

Apple Health doesn't have a direct REST API - data must be exported from
the Health app or accessed via HealthKit on iOS. This client handles:
1. Parsing Apple Health XML exports
2. Processing data synced via a companion iOS shortcut/app
3. Accepting manual data pushes from the iOS Health app
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, date


class AppleHealthClient:
    """Client for processing Apple Health data exports and synced data."""

    # HealthKit quantity type identifiers mapped to our field names
    TYPE_MAP = {
        "HKQuantityTypeIdentifierStepCount": "steps",
        "HKQuantityTypeIdentifierActiveEnergyBurned": "active_calories",
        "HKQuantityTypeIdentifierBasalEnergyBurned": "basal_calories",
        "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance_km",
        "HKQuantityTypeIdentifierHeartRate": "heart_rate",
        "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate",
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv_ms",
        "HKQuantityTypeIdentifierOxygenSaturation": "spo2_pct",
        "HKQuantityTypeIdentifierRespiratoryRate": "respiratory_rate",
        "HKQuantityTypeIdentifierBodyMass": "weight_kg",
        "HKQuantityTypeIdentifierBodyFatPercentage": "body_fat_pct",
        "HKQuantityTypeIdentifierLeanBodyMass": "lean_body_mass_kg",
        "HKQuantityTypeIdentifierBodyMassIndex": "bmi",
        "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_minutes",
        "HKCategoryTypeIdentifierSleepAnalysis": "sleep",
        "HKQuantityTypeIdentifierDietaryWater": "water_ml",
        "HKQuantityTypeIdentifierDietaryEnergyConsumed": "dietary_calories",
        "HKQuantityTypeIdentifierDietaryProtein": "dietary_protein_g",
        "HKQuantityTypeIdentifierDietaryCarbohydrates": "dietary_carbs_g",
        "HKQuantityTypeIdentifierDietaryFatTotal": "dietary_fat_g",
    }

    def parse_export_xml(self, xml_path):
        """Parse an Apple Health XML export file.

        Returns a dict of daily aggregated data keyed by date string.
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()
        daily_data = {}

        for record in root.iter("Record"):
            record_type = record.get("type")
            if record_type not in self.TYPE_MAP:
                continue

            field = self.TYPE_MAP[record_type]
            value = float(record.get("value", 0))
            start_date = record.get("startDate", "")[:10]  # YYYY-MM-DD

            if start_date not in daily_data:
                daily_data[start_date] = {
                    "date": start_date, "source": "apple_health",
                    "steps": 0, "active_calories": 0, "distance_km": 0,
                    "exercise_minutes": 0, "heart_rates": [], "water_ml": 0,
                }

            day = daily_data[start_date]

            if field in ("steps", "active_calories", "exercise_minutes", "water_ml"):
                day[field] = day.get(field, 0) + value
            elif field == "distance_km":
                day[field] = day.get(field, 0) + value / 1000  # meters to km
            elif field == "heart_rate":
                day.setdefault("heart_rates", []).append(value)
            elif field in ("resting_heart_rate", "hrv_ms", "weight_kg",
                           "body_fat_pct", "bmi", "spo2_pct"):
                day[field] = value  # take latest value

        # Compute heart rate averages
        for day_data in daily_data.values():
            hrs = day_data.pop("heart_rates", [])
            if hrs:
                day_data["avg_heart_rate"] = int(sum(hrs) / len(hrs))
                day_data["max_heart_rate"] = int(max(hrs))
                day_data["resting_heart_rate"] = day_data.get(
                    "resting_heart_rate", int(min(hrs)))

        return daily_data

    def process_sync_payload(self, payload):
        """Process a JSON payload pushed from an iOS Shortcut.

        Expected payload format:
        {
            "date": "2024-01-15",
            "steps": 8500,
            "active_calories": 450,
            "exercise_minutes": 45,
            "resting_heart_rate": 58,
            "hrv_ms": 65.2,
            "sleep_hours": 7.5,
            "weight_kg": 75.2,
            ...
        }
        """
        if isinstance(payload, str):
            payload = json.loads(payload)

        data = {"source": "apple_health"}

        field_map = {
            "date": "date", "steps": "steps",
            "active_calories": "active_calories",
            "exercise_minutes": "exercise_minutes",
            "resting_heart_rate": "resting_heart_rate",
            "hrv_ms": "hrv_ms", "sleep_hours": "sleep_hours",
            "weight_kg": "weight_kg", "body_fat_pct": "body_fat_pct",
            "distance_km": "distance_km", "avg_heart_rate": "avg_heart_rate",
            "max_heart_rate": "max_heart_rate", "water_ml": "water_ml",
            "spo2_pct": "spo2_pct", "bmi": "bmi",
        }

        for src_key, dst_key in field_map.items():
            if src_key in payload:
                data[dst_key] = payload[src_key]

        return data

    def get_daily_data(self, target_date=None):
        """Return a template for manually-entered Apple Health data."""
        target = target_date or date.today()
        return {
            "date": target.isoformat(),
            "source": "apple_health",
            "steps": 0,
            "active_calories": 0,
            "distance_km": 0,
            "exercise_minutes": 0,
            "resting_heart_rate": None,
            "avg_heart_rate": None,
            "hrv_ms": None,
            "sleep_hours": None,
            "water_ml": 0,
        }
