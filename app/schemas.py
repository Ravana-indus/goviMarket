"""Shapes shared by the parser, matcher and API."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["farmer", "buyer", "unknown"]
Lang = Literal["si", "ta", "en"]


class Item(BaseModel):
    crop: str = Field(description="Crop in lowercase English, singular, e.g. 'carrot', 'leeks', 'beans', 'tomato'.")
    qty_kg: float = Field(description="Quantity converted to kilograms. 1 sack (gona/uru) of carrot ~ 50 kg unless stated.")
    grade: Optional[str] = Field(description="Quality grade if stated (e.g. 'A', 'export'), else null.")
    price_lkr_per_kg: Optional[float] = Field(description="Price per kg if the sender named one, else null.")


class ParsedMessage(BaseModel):
    """What Gemini returns for any inbound order or harvest message."""
    role: Role = Field(description="'farmer' if offering harvest, 'buyer' if placing an order.")
    language: Lang = Field(description="Language the sender wrote or spoke in.")
    sender_name: Optional[str] = Field(description="Business or person name if visible, else null.")
    location: Optional[str] = Field(description="Town or district in English, e.g. 'Nuwara Eliya', 'Colombo 03'.")
    when: Optional[date] = Field(description="Harvest-ready date (farmer) or needed-by date (buyer), ISO format, else null.")
    items: list[Item]
    unclear: list[str] = Field(description="Fields you could not read or had to guess. Empty if everything was clear.")
    confidence: float = Field(description="0 to 1. Your confidence that the items and quantities are correct.")
    summary_in_sender_language: str = Field(description="One-sentence confirmation of what you understood, in the sender's language.")


class Listing(BaseModel):
    id: str
    farmer: str
    location: str
    crop: str
    qty_kg: float
    ready_on: date
    remaining_kg: float


class Order(BaseModel):
    id: str
    buyer: str
    location: str
    crop: str
    qty_kg: float
    needed_by: date
    remaining_kg: float


class Lane(BaseModel):
    origin: str
    dest: str
    mode: Literal["night_bus", "train_parcel", "sl_post", "lorry"]
    lkr_per_kg: float
    min_charge_lkr: float
    departs: str  # "21:30"
    transit_hours: float
    max_kg: float
    source: str  # where the number came from; "ESTIMATE" until field-checked


class Match(BaseModel):
    listing_id: str
    order_id: str
    farmer: str
    buyer: str
    crop: str
    qty_kg: float
    lane: Optional[Lane]
    transport_lkr_per_kg: float
    farmer_gets_lkr_per_kg: float
    buyer_pays_lkr_per_kg: float
    collector_pays_lkr_per_kg: float
    market_retail_lkr_per_kg: float
