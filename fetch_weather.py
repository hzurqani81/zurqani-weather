import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# -------------------------
# CONFIG (edit if needed)
# -------------------------
PLACE_NAME = "Monticello, AR"
LAT = 33.6289
LON = -91.7909
TIMEZONE = "America/Chicago"

OUTFILE = "weather.json"


def _now_utc_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "+00:00"


def _c_to_f(c):
    return (c * 9.0 / 5.0) + 32.0


def _safe_float(x):
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def _safe_int(x):
    try:
        return None if x is None else int(round(float(x)))
    except Exception:
        return None


def fetch_open_meteo(lat, lon, tz):
    """
    Pulls:
      - current: temperature, apparent temperature, humidity, wind speed, weather code, wind direction, wind gust
      - hourly (next 48h, we’ll keep next 24): temp, apparent temp, precip prob, wind speed, wind dir, wind gust, weather code
      - daily (7d): tmax, tmin, precip prob max, weather code
    """
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": tz,

        # current
        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "weather_code"
        ]),

        # hourly
        "hourly": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "precipitation_probability",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "weather_code"
        ]),

        # daily
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "weather_code"
        ]),

        "forecast_days": 7
    }

    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()


def build_json(raw, place_name, lat, lon, tz):
    meta = {
        "place_name": place_name,
        "lat": lat,
        "lon": lon,
        "timezone": tz,
        "source": "open-meteo",
        "generated_utc": _now_utc_iso()
    }

    # -------- current --------
    cur = raw.get("current", {}) or {}
    current = {
        "temperature_c": _safe_float(cur.get("temperature_2m")),
        "feels_like_c": _safe_float(cur.get("apparent_temperature")),
        "humidity_pct": _safe_int(cur.get("relative_humidity_2m")),
        "wind_speed_kmh": _safe_float(cur.get("wind_speed_10m")),
        "wind_dir_deg": _safe_int(cur.get("wind_direction_10m")),
        "wind_gust_kmh": _safe_float(cur.get("wind_gusts_10m")),
        "weather_code": _safe_int(cur.get("weather_code")),
    }

    # -------- hourly --------
    hourly = []
    h = raw.get("hourly", {}) or {}
    times = h.get("time", []) or []

    temp = h.get("temperature_2m", []) or []
    feels = h.get("apparent_temperature", []) or []
    pop = h.get("precipitation_probability", []) or []
    wind = h.get("wind_speed_10m", []) or []
    wdir = h.get("wind_direction_10m", []) or []
    gust = h.get("wind_gusts_10m", []) or []
    wcode = h.get("weather_code", []) or []

    # Keep next 24 hours from "now" in local tz
    # Open-Meteo already returns times in tz, so we just take first 24 entries.
    keep = min(24, len(times))

    for i in range(keep):
        hourly.append({
            "time": times[i],  # local time string like "2026-01-28T17:00"
            "temperature_c": _safe_float(temp[i]) if i < len(temp) else None,
            "feels_like_c": _safe_float(feels[i]) if i < len(feels) else None,
            "precip_prob_pct": _safe_int(pop[i]) if i < len(pop) else None,
            "wind_speed_kmh": _safe_float(wind[i]) if i < len(wind) else None,
            "wind_dir_deg": _safe_int(wdir[i]) if i < len(wdir) else None,
            "wind_gust_kmh": _safe_float(gust[i]) if i < len(gust) else None,
            "weather_code": _safe_int(wcode[i]) if i < len(wcode) else None,
        })

    # -------- daily --------
    daily = []
    d = raw.get("daily", {}) or {}
    d_dates = d.get("time", []) or []
    tmax = d.get("temperature_2m_max", []) or []
    tmin = d.get("temperature_2m_min", []) or []
    dpop = d.get("precipitation_probability_max", []) or []
    dcode = d.get("weather_code", []) or []

    for i in range(min(7, len(d_dates))):
        daily.append({
            "date": d_dates[i],
            "tmax_c": _safe_float(tmax[i]) if i < len(tmax) else None,
            "tmin_c": _safe_float(tmin[i]) if i < len(tmin) else None,
            "weather_code": _safe_int(dcode[i]) if i < len(dcode) else None,
            "precip_prob_pct": _safe_int(dpop[i]) if i < len(dpop) else None,
        })

    return {"meta": meta, "current": current, "hourly": hourly, "daily": daily}


def main():
    try:
        raw = fetch_open_meteo(LAT, LON, TIMEZONE)
        out = build_json(raw, PLACE_NAME, LAT, LON, TIMEZONE)
        with open(OUTFILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"Wrote {OUTFILE}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
