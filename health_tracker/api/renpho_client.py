"""Renpho smart scale API client for body composition data."""

import requests
import hashlib
from datetime import datetime, date


class RenphoClient:
    """Client for the Renpho API to fetch body composition measurements."""

    BASE_URL = "https://renpho.qnclouds.com/api"
    LOGIN_URL = f"{BASE_URL}/v3/users/sign_in.json"
    MEASUREMENTS_URL = f"{BASE_URL}/v2/measurements/list.json"
    DEVICE_USERS_URL = f"{BASE_URL}/v2/device_users/list.json"

    def __init__(self, email=None, password=None, session_key=None):
        self.email = email
        self.password = password
        self.session_key = session_key
        self.user_id = None

    def login(self):
        """Authenticate with Renpho and get session key."""
        if not self.email or not self.password:
            raise ValueError("Email and password required for login")

        resp = requests.post(self.LOGIN_URL, json={
            "secure_flag": 1,
            "email": self.email,
            "password": self.password,
        })
        resp.raise_for_status()
        data = resp.json()

        if data.get("status_code") != "20000":
            raise Exception(f"Renpho login failed: {data.get('status_message')}")

        terminal = data.get("terminal_user_session_key", "")
        self.session_key = terminal
        self.user_id = data.get("id")
        return data

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "terminal_user_session_key": self.session_key or "",
        }

    def get_measurements(self, start_date=None, end_date=None):
        """Fetch body composition measurements for a date range."""
        if not self.session_key:
            self.login()

        params = {}
        if start_date:
            params["date_from"] = start_date.isoformat()
        if end_date:
            params["date_to"] = end_date.isoformat()

        resp = requests.get(self.MEASUREMENTS_URL,
                            headers=self._headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status_code") != "20000":
            # Try re-login
            self.login()
            resp = requests.get(self.MEASUREMENTS_URL,
                                headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()

        return data.get("last_ary", [])

    def get_latest_measurement(self):
        """Get the most recent body composition measurement."""
        measurements = self.get_measurements()
        if not measurements:
            return None
        return self._parse_measurement(measurements[0])

    def _parse_measurement(self, raw):
        """Parse a raw Renpho measurement into our format."""
        return {
            "date": raw.get("time_stamp", date.today().isoformat())[:10],
            "source": "renpho",
            "weight_kg": raw.get("weight"),
            "bmi": raw.get("bmi"),
            "body_fat_pct": raw.get("bodyfat"),
            "muscle_mass_kg": raw.get("muscle"),
            "bone_mass_kg": raw.get("bone"),
            "water_pct": raw.get("water"),
            "visceral_fat": raw.get("vfal"),
            "basal_metabolism": raw.get("bmr"),
            "metabolic_age": raw.get("bodyage"),
            "protein_pct": raw.get("protein"),
            "subcutaneous_fat_pct": raw.get("subfat"),
            "skeletal_muscle_pct": raw.get("sinew"),
        }

    def sync_daily_data(self, target_date=None):
        """Fetch today's body metrics from Renpho."""
        target = target_date or date.today()

        try:
            measurements = self.get_measurements(target, target)
            if measurements:
                return self._parse_measurement(measurements[0])
        except Exception:
            pass

        # Return empty template if no data
        return {
            "date": target.isoformat(),
            "source": "renpho",
            "weight_kg": None,
            "bmi": None,
            "body_fat_pct": None,
            "muscle_mass_kg": None,
        }

    def get_weight_trend(self, days=30):
        """Get weight measurements for the last N days."""
        end = date.today()
        start = date(end.year, end.month, end.day)
        start = date.fromordinal(end.toordinal() - days)

        measurements = self.get_measurements(start, end)
        return [self._parse_measurement(m) for m in measurements]
