"""
state_manager.py — Temporal cooldown ("5-minute rule") state management.
Prevents status flickering when a zone briefly empties.
"""

import time
import logging

logger = logging.getLogger(__name__)


class ZoneState:
    def __init__(self, zone_id, cooldown_seconds=300):
        self.zone_id = zone_id
        self.cooldown_seconds = cooldown_seconds
        self.status = "available"
        self.last_occupied_time = 0.0
        self.last_available_time = time.time()
        self.person_count = 0
        self.occupied_since = None
        self.total_occupied_seconds = 0.0


class StateManager:
    """Manages temporal state for all table zones with configurable cooldown."""

    def __init__(self):
        self.zones: dict[str, ZoneState] = {}
        self._callbacks = []

    def register_callback(self, fn):
        self._callbacks.append(fn)

    def _notify(self, zone_id, old_status, new_status, person_count):
        for cb in self._callbacks:
            try:
                cb(zone_id, old_status, new_status, person_count)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def initialize_zone(self, zone_id, cooldown_seconds=300):
        self.zones[zone_id] = ZoneState(zone_id, cooldown_seconds)

    def update(self, zone_id, is_occupied, person_count=0, cooldown_seconds=None):
        now = time.time()
        if zone_id not in self.zones:
            self.initialize_zone(zone_id, cooldown_seconds or 300)

        state = self.zones[zone_id]
        if cooldown_seconds is not None:
            state.cooldown_seconds = cooldown_seconds

        old_status = state.status
        state.person_count = person_count

        if is_occupied:
            state.last_occupied_time = now
            if state.status != "occupied":
                state.status = "occupied"
                state.occupied_since = now
                self._notify(zone_id, old_status, "occupied", person_count)
            return "occupied"
        else:
            if state.status in ("occupied", "cooldown"):
                elapsed = now - state.last_occupied_time
                if elapsed < state.cooldown_seconds:
                    if state.status != "cooldown":
                        state.status = "cooldown"
                        self._notify(zone_id, old_status, "cooldown", 0)
                    return "cooldown"
                else:
                    if state.occupied_since:
                        state.total_occupied_seconds += state.last_occupied_time - state.occupied_since
                        state.occupied_since = None
                    state.status = "available"
                    state.last_available_time = now
                    self._notify(zone_id, old_status, "available", 0)
                    return "available"
            return "available"

    def get_status(self, zone_id):
        state = self.zones.get(zone_id)
        if state is None:
            return {"status": "unknown", "person_count": 0, "cooldown_remaining": 0}
        cd_rem = max(0, state.cooldown_seconds - (time.time() - state.last_occupied_time)) \
            if state.status == "cooldown" else 0
        return {
            "status": state.status,
            "person_count": state.person_count,
            "cooldown_remaining": cd_rem,
        }

    def get_all_statuses(self):
        return {zid: self.get_status(zid) for zid in self.zones}

    def get_summary(self):
        total = len(self.zones)
        occupied = sum(1 for s in self.zones.values() if s.status == "occupied")
        cooldown = sum(1 for s in self.zones.values() if s.status == "cooldown")
        available = total - occupied - cooldown
        return {
            "total": total,
            "occupied": occupied,
            "cooldown": cooldown,
            "available": available,
            "pct": round(occupied / total * 100, 1) if total > 0 else 0.0,
        }
