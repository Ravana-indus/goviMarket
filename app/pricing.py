"""Price split: how much of the middleman's spread goes back to farmer and buyer."""
from __future__ import annotations

import json
import os
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Share of the collector-to-retail spread handed back to the buyer as a discount.
BUYER_DISCOUNT_SHARE = float(os.getenv("BUYER_DISCOUNT_SHARE", "0.25"))
# Govi's platform fee as a share of what the buyer pays.
GOVI_FEE = float(os.getenv("GOVI_FEE", "0.05"))


def load_prices(path: Path = DATA / "prices.json") -> dict[str, dict]:
    return {row["crop"]: row for row in json.loads(path.read_text())}


def split(price: dict, transport_lkr_per_kg: float) -> dict:
    """Rs/kg for each party on one matched kg.

    `price` has `collector` (what the village collector pays the farmer today) and
    `retail` (what a Colombo buyer pays today)."""
    collector, retail = price["collector"], price["retail"]
    buyer_pays = round(retail - BUYER_DISCOUNT_SHARE * (retail - collector), 1)
    farmer_gets = round(buyer_pays * (1 - GOVI_FEE) - transport_lkr_per_kg, 1)
    return {
        "buyer_pays": buyer_pays,
        "farmer_gets": farmer_gets,
        "collector": collector,
        "retail": retail,
        "farmer_better_off": farmer_gets > collector,
    }
