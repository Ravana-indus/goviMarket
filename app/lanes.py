"""Pick the cheapest public-transport lane that arrives before the buyer's deadline."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .schemas import Lane

DATA = Path(__file__).resolve().parent.parent / "data"


def load_lanes(path: Path = DATA / "lanes.json") -> list[Lane]:
    return [Lane(**row) for row in json.loads(path.read_text())]


def _norm(place: str) -> str:
    return place.lower().split(",")[0].strip()


# One tuk or small lorry run from the Colombo station or bus stand to the buyers, per consignment.
DEST_PICKUP_LKR = float(os.getenv("DEST_PICKUP_LKR", "1500"))


def lane_cost(lane: Lane, kg: float) -> float:
    """Door-to-door cost of one consignment: freight, plus fixed handling at each end."""
    pickup = 0 if lane.door_delivery else DEST_PICKUP_LKR
    return max(lane.min_charge_lkr, lane.lkr_per_kg * kg) + lane.handling_lkr + pickup


def arrival(lane: Lane, ship_on: date) -> datetime:
    hh, mm = (int(x) for x in lane.departs.split(":"))
    return datetime(ship_on.year, ship_on.month, ship_on.day, hh, mm) + timedelta(hours=lane.transit_hours)


def pick_lane(lanes: list[Lane], *, origin: str, dest: str, kg: float,
              ship_on: date, needed_by: date) -> Optional[Lane]:
    """Cheapest lane on this route that fits the load and lands by 08:00 on `needed_by`."""
    deadline = datetime(needed_by.year, needed_by.month, needed_by.day, 8, 0)
    ok = [l for l in lanes
          if _norm(l.origin) == _norm(origin) and _norm(l.dest) == _norm(dest)
          and l.max_kg >= kg and arrival(l, ship_on) <= deadline]
    return min(ok, key=lambda l: lane_cost(l, kg), default=None)


def cheapest_to(lanes: list[Lane], *, origin: str, dest: str, kg: float) -> Optional[Lane]:
    """Cheapest lane on a route for a load, ignoring deadlines (for price quotes)."""
    ok = [l for l in lanes if _norm(l.origin) == _norm(origin) and _norm(l.dest) == _norm(dest) and l.max_kg >= kg]
    return min(ok, key=lambda l: lane_cost(l, kg), default=None)
