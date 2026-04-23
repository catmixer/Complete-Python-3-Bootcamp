"""Place Lookup Maps App.

Enter a place name and get a Google Maps link, full address, a short
description, and distance + time from your location by car, transit,
and walking.

Data sources:
  * Nominatim (OpenStreetMap)         - geocoding + full address   [free]
  * Wikipedia REST API                - description of the place   [free]
  * Google Maps Distance Matrix API   - car/transit/walking times  [needs API key]
  * OSRM public demo                  - car/walking fallback       [free]
  * ipapi.co                          - detect user location       [free]
  * Google Maps URL scheme            - deep links per travel mode [free]

Supply a Google Maps API key via --api-key or the GOOGLE_MAPS_API_KEY
environment variable to get real transit times and consistent, accurate
results for all three modes. Without a key the app falls back to OSRM
for driving + walking and shows a Google Maps link (no time) for transit.

Usage:
    python place_lookup.py "Eiffel Tower"
    python place_lookup.py "Shibuya Crossing" --from "Tokyo Station"
    python place_lookup.py "Colosseum" --from "41.9028,12.4964"
    GOOGLE_MAPS_API_KEY=AIza... python place_lookup.py "Grand Central"
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from urllib.parse import quote_plus, urlencode

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OSRM_URL = "https://router.project-osrm.org"
IP_LOOKUP_URL = "https://ipapi.co/json/"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
GOOGLE_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

USER_AGENT = "place-lookup-maps-app/1.0 (+https://github.com/catmixer/complete-python-3-bootcamp)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en"}

# Fallback average speeds when a routing provider is unreachable.
WALKING_SPEED_KMH = 5.0
DRIVING_SPEED_KMH = 50.0
ROUTE_DETOUR_FACTOR = 1.3  # roads are longer than straight lines


# ---------- API helpers ----------


def geocode(query: str) -> dict | None:
    """Look up a place name via Nominatim. Returns the top result or None."""
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }
    r = requests.get(f"{NOMINATIM_URL}/search", params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    results = r.json()
    return results[0] if results else None


def detect_ip_location() -> tuple[float, float, str] | None:
    """Best-effort detect the user's location from their public IP."""
    try:
        r = requests.get(IP_LOOKUP_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is None or lon is None:
            return None
        city = data.get("city") or ""
        region = data.get("region") or ""
        country = data.get("country_name") or ""
        label = ", ".join(p for p in (city, region, country) if p) or "detected location"
        return float(lat), float(lon), label
    except (requests.RequestException, ValueError):
        return None


def wikipedia_summary(title: str) -> str | None:
    """Return a short Wikipedia summary for `title`, if one exists."""
    if not title:
        return None
    try:
        r = requests.get(
            WIKIPEDIA_SUMMARY_URL + quote_plus(title.replace(" ", "_")),
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("type") == "disambiguation":
            return None
        return data.get("extract")
    except (requests.RequestException, ValueError):
        return None


def google_distance_matrix(
    origin: tuple[float, float],
    destination: tuple[float, float],
    mode: str,
    api_key: str,
) -> dict | None:
    """Query Google Maps Distance Matrix for distance/duration.

    mode is one of 'driving', 'transit', 'walking', 'bicycling'.
    Returns {'distance_m', 'duration_s', 'source': 'google'} or None on
    any non-OK result (including ZERO_RESULTS — e.g. no transit in area).
    """
    params = {
        "origins": f"{origin[0]},{origin[1]}",
        "destinations": f"{destination[0]},{destination[1]}",
        "mode": mode,
        "units": "metric",
        "key": api_key,
    }
    try:
        r = requests.get(GOOGLE_DISTANCE_MATRIX_URL, params=params, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("status") != "OK" or not data.get("rows"):
            return None
        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return None
        return {
            "distance_m": float(element["distance"]["value"]),
            "duration_s": float(element["duration"]["value"]),
            "source": "google",
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def osrm_route(origin: tuple[float, float], destination: tuple[float, float], profile: str) -> dict | None:
    """Query OSRM for distance (metres) and duration (seconds).

    profile is a server-configured OSRM profile; the public demo accepts
    'driving', 'walking' (alias 'foot'), and 'cycling' (alias 'bike').
    """
    lat1, lon1 = origin
    lat2, lon2 = destination
    url = f"{OSRM_URL}/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}"
    try:
        r = requests.get(url, params={"overview": "false"}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        return {"distance_m": float(route["distance"]), "duration_s": float(route["duration"])}
    except (requests.RequestException, ValueError):
        return None


# ---------- Formatting ----------


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def format_distance(meters: float | None) -> str:
    if meters is None:
        return "—"
    if meters < 1000:
        return f"{int(round(meters))} m"
    return f"{meters / 1000:.1f} km"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    mins = int(round(seconds / 60))
    if mins < 1:
        return "<1 min"
    if mins < 60:
        return f"{mins} min"
    hours, m = divmod(mins, 60)
    return f"{hours} h {m:02d} min"


def estimate(distance_km: float, speed_kmh: float) -> dict:
    """Rough fallback when a routing provider is unavailable."""
    road_km = distance_km * ROUTE_DETOUR_FACTOR
    return {
        "distance_m": road_km * 1000,
        "duration_s": (road_km / speed_kmh) * 3600,
        "estimated": True,
    }


# ---------- Google Maps link builders ----------


def _fmt_point(point) -> str:
    if isinstance(point, tuple):
        return f"{point[0]},{point[1]}"
    return str(point)


def google_maps_place_link(lat: float, lon: float, name: str | None = None) -> str:
    if name:
        return "https://www.google.com/maps/search/?" + urlencode(
            {"api": "1", "query": f"{name} ({lat},{lon})"}, quote_via=quote_plus
        )
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": "1", "query": f"{lat},{lon}"}, quote_via=quote_plus
    )


def google_maps_directions_link(origin, destination, mode: str) -> str:
    params = {
        "api": "1",
        "origin": _fmt_point(origin),
        "destination": _fmt_point(destination),
        "travelmode": mode,
    }
    return "https://www.google.com/maps/dir/?" + urlencode(params, quote_via=quote_plus)


# ---------- Core orchestration ----------


def describe_place(place: dict) -> str | None:
    parts = []
    extra = place.get("extratags") or {}
    if extra.get("description"):
        parts.append(extra["description"])
    category = place.get("category")
    ptype = place.get("type")
    if category and ptype:
        parts.append(f"{category}/{ptype}".replace("_", " "))
    return " · ".join(parts) or None


def pick_wiki_title(place: dict) -> str | None:
    extra = place.get("extratags") or {}
    wiki = extra.get("wikipedia")
    if wiki and ":" in wiki:
        return wiki.split(":", 1)[1]
    names = place.get("namedetails") or {}
    return names.get("name:en") or names.get("name") or None


def resolve_origin(origin_arg: str | None) -> tuple[float, float, str]:
    if origin_arg is None:
        detected = detect_ip_location()
        if detected is None:
            raise SystemExit(
                "Could not auto-detect your location. Pass --from 'city name' or --from 'lat,lon'."
            )
        return detected
    # Try "lat,lon" form first.
    if "," in origin_arg:
        try:
            lat_str, lon_str = [p.strip() for p in origin_arg.split(",", 1)]
            return float(lat_str), float(lon_str), origin_arg
        except ValueError:
            pass
    place = geocode(origin_arg)
    if not place:
        raise SystemExit(f"Could not find origin location: {origin_arg!r}")
    return float(place["lat"]), float(place["lon"]), place["display_name"]


def travel_info(
    origin,
    destination,
    straight_km: float,
    api_key: str | None = None,
) -> dict[str, dict | None]:
    """Return {'driving', 'transit', 'walking'} each mapped to a result dict.

    Result dict has 'distance_m', 'duration_s', optional 'source' and
    'estimated'. Transit may be None if we can't compute it (no API key
    or no transit available) — callers should fall back to a deep link.
    """
    results: dict[str, dict | None] = {}

    driving = None
    walking = None
    transit = None

    if api_key:
        driving = google_distance_matrix(origin, destination, "driving", api_key)
        transit = google_distance_matrix(origin, destination, "transit", api_key)
        walking = google_distance_matrix(origin, destination, "walking", api_key)

    if driving is None:
        driving = osrm_route(origin, destination, "driving")
    if driving is None:
        driving = estimate(straight_km, DRIVING_SPEED_KMH)

    if walking is None:
        walking = osrm_route(origin, destination, "walking") or osrm_route(origin, destination, "foot")
    if walking is None:
        walking = estimate(straight_km, WALKING_SPEED_KMH)

    results["driving"] = driving
    results["transit"] = transit  # may be None → caller shows link only
    results["walking"] = walking
    return results


def run(destination_query: str, origin_arg: str | None, api_key: str | None = None) -> int:
    print(f"Looking up: {destination_query}\n")
    place = geocode(destination_query)
    if place is None:
        print(f"No results found for {destination_query!r}.")
        return 1

    dest_lat = float(place["lat"])
    dest_lon = float(place["lon"])
    dest = (dest_lat, dest_lon)
    display_name = place.get("display_name", destination_query)
    primary_name = (place.get("namedetails") or {}).get("name") or display_name.split(",")[0].strip()

    description = describe_place(place)
    summary = wikipedia_summary(pick_wiki_title(place))

    origin_lat, origin_lon, origin_label = resolve_origin(origin_arg)
    origin = (origin_lat, origin_lon)

    straight_km = haversine_km(origin, dest)
    travel = travel_info(origin, dest, straight_km, api_key=api_key)

    bar = "=" * 72
    print(bar)
    print(f"Destination : {primary_name}")
    print(f"Address     : {display_name}")
    if description:
        print(f"Category    : {description}")
    print(f"Coordinates : {dest_lat:.5f}, {dest_lon:.5f}")
    print(f"Google Maps : {google_maps_place_link(dest_lat, dest_lon, primary_name)}")
    if summary:
        print("\nAbout:")
        for line in _wrap(summary, 70):
            print(f"  {line}")
    print()
    print(f"From        : {origin_label}  ({origin_lat:.5f}, {origin_lon:.5f})")
    print(f"Straight-line distance: {straight_km:.1f} km")
    print()
    print("Travel from your location:")
    print(f"  {'Mode':<14}{'Distance':>10}   {'Time':>12}")

    for label, key, gmaps_mode in [
        ("By car",     "driving", "driving"),
        ("By transit", "transit", "transit"),
        ("Walking",    "walking", "walking"),
    ]:
        r = travel.get(key)
        if r is None:
            dist_s = "—"
            time_s = "see link"
            note = ""
        else:
            dist_s = format_distance(r["distance_m"])
            time_s = format_duration(r["duration_s"])
            if r.get("estimated"):
                note = "  (est.)"
            elif r.get("source") == "google":
                note = "  (google)"
            else:
                note = ""
        print(f"  {label:<14}{dist_s:>10}   {time_s:>12}{note}")
        print(f"    {google_maps_directions_link(origin, dest, gmaps_mode)}")
    if api_key is None:
        print()
        print("  Tip: set GOOGLE_MAPS_API_KEY (or pass --api-key) for real transit times.")
    print(bar)
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > width:
            if current:
                lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Look up a place: Google Maps link, full address, description, and travel info."
    )
    parser.add_argument("destination", nargs="+", help="Name of the place / destination.")
    parser.add_argument(
        "--from",
        dest="origin",
        default=None,
        help="Your starting location (address or 'lat,lon'). Auto-detected from IP if omitted.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="Google Maps API key. Falls back to $GOOGLE_MAPS_API_KEY if unset.",
    )
    args = parser.parse_args(argv)

    query = " ".join(args.destination).strip()
    if not query:
        parser.error("destination is required")

    api_key = args.api_key or os.environ.get("GOOGLE_MAPS_API_KEY") or None

    try:
        return run(query, args.origin, api_key=api_key)
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
