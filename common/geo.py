"""Geo helpers shared by trajectory (M4) and anomaly detection (M5)."""
from math import radians, sin, cos, asin, sqrt


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    d = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(d))


def implausible_speed(dist_km, seconds, max_kmph=200):
    """True if covering dist_km in `seconds` implies an impossible speed."""
    if seconds <= 0:
        return dist_km > 0.05  # two cameras, same instant, different places
    return (dist_km / (seconds / 3600)) > max_kmph
