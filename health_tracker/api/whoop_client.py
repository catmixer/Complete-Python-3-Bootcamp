"""Whoop API client for fetching recovery, strain, sleep, and workout data."""

import requests
from datetime import datetime, timedelta


class WhoopClient:
    """Client for the Whoop API v1."""

    BASE_URL = "https://api.prod.whoop.com/developer/v1"
    AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
    TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

    def __init__(self, client_id=None, client_secret=None, access_token=None,
                 refresh_token=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token

    def get_auth_url(self, redirect_uri, scope="read:recovery read:sleep read:workout read:cycles read:body_measurement"):
        """Generate OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scope,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"

    def exchange_code(self, code, redirect_uri):
        """Exchange authorization code for access token."""
        resp = requests.post(self.TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        return data

    def refresh_access_token(self):
        """Refresh the access token."""
        resp = requests.post(self.TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        return data

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def _get(self, endpoint, params=None):
        """Make authenticated GET request with auto-refresh on 401."""
        resp = requests.get(f"{self.BASE_URL}{endpoint}",
                            headers=self._headers(), params=params)
        if resp.status_code == 401 and self.refresh_token:
            self.refresh_access_token()
            resp = requests.get(f"{self.BASE_URL}{endpoint}",
                                headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_recovery(self, start_date=None, end_date=None):
        """Get recovery scores for a date range."""
        params = {}
        if start_date:
            params["start"] = start_date.isoformat() + "T00:00:00.000Z"
        if end_date:
            params["end"] = end_date.isoformat() + "T23:59:59.999Z"
        return self._get("/recovery", params)

    def get_sleep(self, start_date=None, end_date=None):
        """Get sleep data for a date range."""
        params = {}
        if start_date:
            params["start"] = start_date.isoformat() + "T00:00:00.000Z"
        if end_date:
            params["end"] = end_date.isoformat() + "T23:59:59.999Z"
        return self._get("/activity/sleep", params)

    def get_workouts(self, start_date=None, end_date=None):
        """Get workout data for a date range."""
        params = {}
        if start_date:
            params["start"] = start_date.isoformat() + "T00:00:00.000Z"
        if end_date:
            params["end"] = end_date.isoformat() + "T23:59:59.999Z"
        return self._get("/activity/workout", params)

    def get_cycles(self, start_date=None, end_date=None):
        """Get physiological cycles (strain) data."""
        params = {}
        if start_date:
            params["start"] = start_date.isoformat() + "T00:00:00.000Z"
        if end_date:
            params["end"] = end_date.isoformat() + "T23:59:59.999Z"
        return self._get("/cycle", params)

    def get_body_measurement(self):
        """Get the latest body measurement."""
        return self._get("/body_measurement")

    def sync_daily_data(self, target_date=None):
        """Fetch all daily data and return a unified dictionary."""
        target = target_date or datetime.utcnow().date()
        data = {
            "date": target.isoformat(),
            "source": "whoop",
        }

        try:
            recovery = self.get_recovery(target, target)
            if recovery.get("records"):
                rec = recovery["records"][0]
                score = rec.get("score", {})
                data["recovery_score"] = score.get("recovery_score")
                data["resting_heart_rate"] = score.get("resting_heart_rate")
                data["hrv_ms"] = score.get("hrv_rmssd_milli")
                data["spo2_pct"] = score.get("spo2_percentage")
                data["skin_temp_celsius"] = score.get("skin_temp_celsius")
        except Exception:
            pass

        try:
            sleep = self.get_sleep(target, target)
            if sleep.get("records"):
                slp = sleep["records"][0]
                score = slp.get("score", {})
                stage = score.get("stage_summary", {})
                data["sleep_hours"] = score.get("total_in_bed_time_milli", 0) / 3600000
                data["sleep_quality_score"] = score.get("sleep_performance_percentage")
                data["rem_sleep_hours"] = stage.get("total_rem_sleep_time_milli", 0) / 3600000
                data["deep_sleep_hours"] = stage.get("total_slow_wave_sleep_time_milli", 0) / 3600000
                data["light_sleep_hours"] = stage.get("total_light_sleep_time_milli", 0) / 3600000
                data["respiratory_rate"] = score.get("respiratory_rate")
        except Exception:
            pass

        try:
            cycles = self.get_cycles(target, target)
            if cycles.get("records"):
                cyc = cycles["records"][0]
                score = cyc.get("score", {})
                data["strain_score"] = score.get("strain")
                data["active_calories"] = score.get("kilojoule", 0) / 4.184
                data["avg_heart_rate"] = score.get("average_heart_rate")
                data["max_heart_rate"] = score.get("max_heart_rate")
        except Exception:
            pass

        try:
            workouts = self.get_workouts(target, target)
            if workouts.get("records"):
                total_minutes = 0
                total_calories = 0
                for w in workouts["records"]:
                    score = w.get("score", {})
                    total_minutes += (score.get("end", 0) - score.get("start", 0)) / 60000
                    total_calories += score.get("kilojoule", 0) / 4.184
                data["exercise_minutes"] = int(total_minutes)
                data["total_calories_burned"] = total_calories
        except Exception:
            pass

        return data
