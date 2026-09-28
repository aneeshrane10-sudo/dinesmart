"""
Zone Logic — Spatial intersection calculator using Shapely.
Determines if detected person bounding boxes overlap with defined table zone polygons.
"""

import logging
from shapely.geometry import Polygon, box as shapely_box
from shapely.validation import make_valid

logger = logging.getLogger(__name__)


def create_zone_polygon(coords):
    """
    Create a Shapely Polygon from a list of [x, y] coordinate pairs.

    Args:
        coords: List of [x, y] pairs, e.g. [[100,100], [200,100], [200,200], [100,200]]

    Returns:
        shapely.geometry.Polygon or None if invalid
    """
    try:
        if len(coords) < 3:
            logger.warning(f"Zone needs at least 3 points, got {len(coords)}")
            return None
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        return poly
    except Exception as e:
        logger.error(f"Error creating zone polygon: {e}")
        return None


def create_person_box(bbox):
    """
    Create a Shapely box from a person bounding box.

    Args:
        bbox: [x1, y1, x2, y2] coordinates

    Returns:
        shapely.geometry.Polygon (rectangle)
    """
    x1, y1, x2, y2 = bbox
    return shapely_box(x1, y1, x2, y2)


def compute_overlap_ratio(zone_poly, person_poly):
    """
    Compute what fraction of the person bounding box overlaps with the zone.

    Returns:
        float: 0.0 to 1.0 overlap ratio
    """
    try:
        if not zone_poly.intersects(person_poly):
            return 0.0
        intersection_area = zone_poly.intersection(person_poly).area
        person_area = person_poly.area
        if person_area == 0:
            return 0.0
        return intersection_area / person_area
    except Exception as e:
        logger.error(f"Overlap computation error: {e}")
        return 0.0


def check_occupancy(person_detections, table_zones, overlap_threshold=0.25):
    """
    Check which table zones are occupied by detected persons.

    Args:
        person_detections: List of dicts with "bbox" key: [x1, y1, x2, y2]
        table_zones: List of dicts with "zone_id", "polygon_coords", "label" keys
        overlap_threshold: Minimum overlap ratio to count as "in zone" (default 25%)

    Returns:
        Dict: {zone_id: {"occupied": bool, "person_count": int, "avg_confidence": float, "track_ids": list}}
    """
    results = {}

    for zone in table_zones:
        zone_id = zone["zone_id"]
        zone_poly = create_zone_polygon(zone["polygon_coords"])

        if zone_poly is None:
            results[zone_id] = {
                "occupied": False,
                "person_count": 0,
                "avg_confidence": 0.0,
                "track_ids": [],
            }
            continue

        persons_in_zone = []
        track_ids = []
        total_confidence = 0.0

        for person in person_detections:
            person_poly = create_person_box(person["bbox"])
            overlap = compute_overlap_ratio(zone_poly, person_poly)

            if overlap >= overlap_threshold:
                persons_in_zone.append(person)
                total_confidence += person.get("confidence", 0.0)
                if person.get("track_id") is not None:
                    track_ids.append(person["track_id"])

        count = len(persons_in_zone)
        results[zone_id] = {
            "occupied": count > 0,
            "person_count": count,
            "avg_confidence": total_confidence / count if count > 0 else 0.0,
            "track_ids": track_ids,
        }

    return results
