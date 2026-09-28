"""
Analytics Engine — Computes occupancy metrics from OccupancySnapshot time-series data.
Generates peak occupancy graphs, average turnover time, heatmaps, and wait time predictions.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


def compute_hourly_occupancy(snapshots, total_tables):
    """
    Compute average occupancy percentage grouped by hour.

    Args:
        snapshots: QuerySet of OccupancySnapshot objects
        total_tables: Total number of table zones

    Returns:
        List of dicts: [{"hour": 0-23, "avg_occupancy_pct": float, "avg_occupied": float}]
    """
    hourly_data = defaultdict(list)

    for snap in snapshots:
        hour = snap.timestamp.hour
        is_occupied = 1 if snap.status == "occupied" else 0
        hourly_data[hour].append(is_occupied)

    result = []
    for hour in range(24):
        entries = hourly_data.get(hour, [])
        if entries:
            avg_occupied = sum(entries) / len(entries) * total_tables
            avg_pct = sum(entries) / len(entries) * 100
        else:
            avg_occupied = 0
            avg_pct = 0

        result.append({
            "hour": hour,
            "hour_label": f"{hour:02d}:00",
            "avg_occupancy_pct": round(avg_pct, 1),
            "avg_occupied_tables": round(avg_occupied, 1),
            "sample_count": len(entries),
        })

    return result


def compute_turnover_times(snapshots_by_zone):
    """
    Calculate average turnover time per zone (how long tables stay occupied).

    Args:
        snapshots_by_zone: Dict {zone_id: [ordered OccupancySnapshot list]}

    Returns:
        Dict: {zone_id: {"avg_turnover_minutes": float, "total_sessions": int}}
    """
    results = {}

    for zone_id, snapshots in snapshots_by_zone.items():
        sessions = []
        current_session_start = None

        for snap in snapshots:
            if snap.status == "occupied" and current_session_start is None:
                current_session_start = snap.timestamp
            elif snap.status == "available" and current_session_start is not None:
                duration = (snap.timestamp - current_session_start).total_seconds() / 60.0
                if duration > 1:  # Ignore very short blips
                    sessions.append(duration)
                current_session_start = None

        avg_minutes = sum(sessions) / len(sessions) if sessions else 0
        results[zone_id] = {
            "avg_turnover_minutes": round(avg_minutes, 1),
            "total_sessions": len(sessions),
        }

    return results


def compute_heatmap_data(snapshots, table_zones):
    """
    Compute heatmap intensity for each zone (how busy each table is).

    Args:
        snapshots: QuerySet of OccupancySnapshot objects
        table_zones: List of zone dicts with zone_id, label

    Returns:
        List of dicts: [{"zone_id": int, "label": str, "intensity": 0.0-1.0, "total_occupied_minutes": float}]
    """
    zone_occupied_counts = defaultdict(int)
    zone_total_counts = defaultdict(int)

    for snap in snapshots:
        zone_id = snap.zone_id
        zone_total_counts[zone_id] += 1
        if snap.status == "occupied":
            zone_occupied_counts[zone_id] += 1

    # Normalize to 0-1
    max_ratio = 0
    ratios = {}
    for zone in table_zones:
        zid = zone["zone_id"]
        total = zone_total_counts.get(zid, 0)
        occupied = zone_occupied_counts.get(zid, 0)
        ratio = occupied / total if total > 0 else 0
        ratios[zid] = ratio
        max_ratio = max(max_ratio, ratio)

    result = []
    for zone in table_zones:
        zid = zone["zone_id"]
        ratio = ratios.get(zid, 0)
        intensity = ratio / max_ratio if max_ratio > 0 else 0

        # Estimate occupied minutes (assuming ~30s between snapshots)
        occupied_count = zone_occupied_counts.get(zid, 0)
        total_minutes = occupied_count * 0.5  # 30-second intervals

        result.append({
            "zone_id": zid,
            "label": zone.get("label", f"Table {zid}"),
            "intensity": round(intensity, 3),
            "occupancy_ratio": round(ratio, 3),
            "total_occupied_minutes": round(total_minutes, 1),
            "polygon_coords": zone.get("polygon_coords", []),
        })

    return result


def estimate_wait_time(zone_id, snapshots_by_zone, current_status, current_hour):
    """
    Predict when a table will become free based on historical data.

    Args:
        zone_id: The table zone to predict for
        snapshots_by_zone: Historical snapshots grouped by zone
        current_status: Current zone status
        current_hour: Current hour (0-23)

    Returns:
        Dict: {"estimated_minutes": float or None, "confidence": str}
    """
    if current_status != "occupied":
        return {"estimated_minutes": 0, "confidence": "high"}

    zone_snaps = snapshots_by_zone.get(zone_id, [])
    if not zone_snaps:
        return {"estimated_minutes": None, "confidence": "no_data"}

    # Filter snapshots from similar time of day (±2 hours)
    relevant_sessions = []
    current_session_start = None

    for snap in zone_snaps:
        snap_hour = snap.timestamp.hour
        hour_diff = min(abs(snap_hour - current_hour), 24 - abs(snap_hour - current_hour))

        if hour_diff <= 2:
            if snap.status == "occupied" and current_session_start is None:
                current_session_start = snap.timestamp
            elif snap.status == "available" and current_session_start is not None:
                duration = (snap.timestamp - current_session_start).total_seconds() / 60.0
                if duration > 1:
                    relevant_sessions.append(duration)
                current_session_start = None

    if not relevant_sessions:
        # Fall back to all sessions
        return {"estimated_minutes": 30, "confidence": "low"}

    avg_duration = sum(relevant_sessions) / len(relevant_sessions)
    confidence = "high" if len(relevant_sessions) >= 5 else "medium"

    return {
        "estimated_minutes": round(avg_duration, 0),
        "confidence": confidence,
    }


def generate_analytics_report(snapshots, table_zones, current_statuses=None):
    """
    Generate a complete analytics report from snapshot data.

    Args:
        snapshots: QuerySet of OccupancySnapshot objects
        table_zones: List of zone dicts
        current_statuses: Dict of current zone statuses (optional)

    Returns:
        Dict with all analytics data
    """
    total_tables = len(table_zones)

    # Group snapshots by zone
    snapshots_by_zone = defaultdict(list)
    for snap in snapshots:
        snapshots_by_zone[snap.zone_id].append(snap)

    # Sort each zone's snapshots by time
    for zid in snapshots_by_zone:
        snapshots_by_zone[zid].sort(key=lambda s: s.timestamp)

    hourly = compute_hourly_occupancy(snapshots, total_tables)
    turnover = compute_turnover_times(snapshots_by_zone)
    heatmap = compute_heatmap_data(snapshots, table_zones)

    # Wait time predictions for occupied tables
    wait_predictions = {}
    current_hour = datetime.now().hour
    if current_statuses:
        for zone in table_zones:
            zid = zone["zone_id"]
            status = current_statuses.get(zid, {}).get("status", "available")
            if status == "occupied":
                wait_predictions[zid] = estimate_wait_time(
                    zid, snapshots_by_zone, status, current_hour
                )

    return {
        "hourly_occupancy": hourly,
        "turnover_times": turnover,
        "heatmap": heatmap,
        "wait_predictions": wait_predictions,
        "total_tables": total_tables,
        "total_snapshots": len(snapshots),
    }
