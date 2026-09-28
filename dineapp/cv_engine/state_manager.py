"""
State Manager — Temporal cooldown logic to prevent status flickering.
Implements the "5-minute rule": when a zone becomes empty, wait N seconds
before switching from "occupied" to "available" to handle temporary absences.
"""

import time
import logging

logger = logging.getLogger(__name__)


class ZoneState:
    """Tracks the temporal state of a single table zone."""

    def __init__(self, zone_id, cooldown_seconds=300):
        self.zone_id = zone_id
        self.cooldown_seconds = cooldown_seconds
        self.status = "available"
        self.last_occupied_time = 0.0
        self.last_available_time = time.time()
        self.person_count = 0
        self.occupied_since = None  # Timestamp when occupancy started
        self.total_occupied_seconds = 0.0

    def __repr__(self):
        return f"ZoneState({self.zone_id}: {self.status}, persons={self.person_count})"


class StateManager:
    """
    Manages temporal state for all table zones.
    Prevents rapid "occupied ↔ available" flickering using cooldown timers.
    """

    def __init__(self):
        self.zones = {}  # {zone_id: ZoneState}
        self._callbacks = []  # List of (callback_fn) for status change events

    def register_callback(self, callback_fn):
        """
        Register a callback for status change events.
        Callback receives: (zone_id, old_status, new_status, person_count)
        """
        self._callbacks.append(callback_fn)

    def _notify(self, zone_id, old_status, new_status, person_count):
        """Fire all registered callbacks on status change."""
        for cb in self._callbacks:
            try:
                cb(zone_id, old_status, new_status, person_count)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def initialize_zone(self, zone_id, cooldown_seconds=300):
        """Initialize or reset a zone's state."""
        self.zones[zone_id] = ZoneState(zone_id, cooldown_seconds)
        logger.debug(f"Initialized zone {zone_id} with cooldown={cooldown_seconds}s")

    def update(self, zone_id, is_occupied, person_count=0, cooldown_seconds=None):
        """
        Update a zone's state based on current detection results.

        Args:
            zone_id: ID of the table zone
            is_occupied: Whether persons are currently detected in the zone
            person_count: Number of persons detected
            cooldown_seconds: Override cooldown (uses zone default if None)

        Returns:
            str: Current status — "occupied", "cooldown", or "available"
        """
        now = time.time()

        # Auto-initialize if zone not yet tracked
        if zone_id not in self.zones:
            cd = cooldown_seconds or 300
            self.initialize_zone(zone_id, cd)

        state = self.zones[zone_id]
        if cooldown_seconds is not None:
            state.cooldown_seconds = cooldown_seconds

        old_status = state.status
        state.person_count = person_count

        if is_occupied:
            # Zone has people → mark as occupied
            state.last_occupied_time = now
            if state.status != "occupied":
                state.status = "occupied"
                state.occupied_since = now
                self._notify(zone_id, old_status, "occupied", person_count)
            return "occupied"

        else:
            # Zone is empty — check cooldown
            if state.status in ("occupied", "cooldown"):
                elapsed = now - state.last_occupied_time

                if elapsed < state.cooldown_seconds:
                    # Still within grace period
                    if state.status != "cooldown":
                        state.status = "cooldown"
                        self._notify(zone_id, old_status, "cooldown", 0)
                    return "cooldown"
                else:
                    # Cooldown expired → truly available
                    if state.occupied_since:
                        state.total_occupied_seconds += (state.last_occupied_time - state.occupied_since)
                        state.occupied_since = None
                    state.status = "available"
                    state.last_available_time = now
                    self._notify(zone_id, old_status, "available", 0)
                    return "available"
            else:
                # Already available
                return "available"

    def get_status(self, zone_id):
        """Get current status of a zone."""
        state = self.zones.get(zone_id)
        if state is None:
            return {"status": "unknown", "person_count": 0}
        return {
            "status": state.status,
            "person_count": state.person_count,
            "cooldown_remaining": max(
                0,
                state.cooldown_seconds - (time.time() - state.last_occupied_time)
            ) if state.status == "cooldown" else 0,
        }

    def get_all_statuses(self):
        """Get status of all tracked zones."""
        return {zid: self.get_status(zid) for zid in self.zones}

    def get_occupancy_summary(self):
        """Get aggregate occupancy stats."""
        total = len(self.zones)
        occupied = sum(1 for s in self.zones.values() if s.status == "occupied")
        cooldown = sum(1 for s in self.zones.values() if s.status == "cooldown")
        available = total - occupied - cooldown
        return {
            "total_tables": total,
            "occupied": occupied,
            "cooldown": cooldown,
            "available": available,
            "occupancy_pct": (occupied / total * 100) if total > 0 else 0,
        }
