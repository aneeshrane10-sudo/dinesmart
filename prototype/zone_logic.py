"""
zone_logic.py — Shapely-based zone intersection calculator.
Determines which table zones contain detected persons.
"""

import logging
from shapely.geometry import Polygon, box as shapely_box
from shapely.validation import make_valid

logger = logging.getLogger(__name__)


def create_zone_polygon(coords):
    if len(coords) < 3:
        return None
    try:
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        return poly
    except Exception as e:
        logger.error(f"Zone polygon error: {e}")
        return None


def compute_overlap_ratio(zone_poly, person_poly):
    try:
        if not zone_poly.intersects(person_poly):
            return 0.0
        inter = zone_poly.intersection(person_poly).area
        area = person_poly.area
        return inter / area if area > 0 else 0.0
    except Exception:
        return 0.0


def check_occupancy(person_detections, table_zones, overlap_threshold=0.25):
    """
    Returns dict: {zone_id: {"occupied": bool, "person_count": int,
                              "avg_confidence": float, "track_ids": list}}
    """
    results = {}
    for zone in table_zones:
        zone_id = zone["zone_id"]
        zone_poly = create_zone_polygon(zone["polygon_coords"])

        if zone_poly is None:
            results[zone_id] = {"occupied": False, "person_count": 0, "avg_confidence": 0.0, "track_ids": []}
            continue

        persons_in = []
        track_ids = []
        total_conf = 0.0

        for p in person_detections:
            pb = shapely_box(*p["bbox"])
            if compute_overlap_ratio(zone_poly, pb) >= overlap_threshold:
                persons_in.append(p)
                total_conf += p.get("confidence", 0.0)
                if p.get("track_id") is not None:
                    track_ids.append(p["track_id"])

        count = len(persons_in)
        results[zone_id] = {
            "occupied": count > 0,
            "person_count": count,
            "avg_confidence": total_conf / count if count > 0 else 0.0,
            "track_ids": track_ids,
        }
    return results
