"""Pick the cheapest public-transport lane that arrives before the buyer's deadline."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .schemas import Lane

DATA = Path(__file__).resolve().parent.parent / "data"


def load_lanes(path: Path = DATA / "lanes.json") -> list[Lane]:
    return [Lane(**row) for row in json.loads(path.read_text())]


def _norm(place: str) -> str:
    return place.lower().split(",")[0].strip()


def lane_cost(lane: Lane, kg: float) -> float:
    return max(lane.min_charge_lkr, lane.lkr_per_kg * kg)


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
