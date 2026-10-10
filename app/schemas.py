"""Shapes shared by the parser, matcher and API."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["farmer", "buyer", "reporter", "unknown"]
PriceKind = Literal["collector", "wholesale", "retail"]
ShipStatus = Literal["planned", "booked", "loaded", "in_transit", "arrived", "delivered", "missed"]
Lang = Literal["si", "ta", "en"]
Intent = Literal["order", "edit", "confirm", "cancel", "status", "chat"]


class Item(BaseModel):
    crop: str = Field(description="Crop in lowercase English, singular, e.g. 'carrot', 'leeks', 'beans', 'tomato'.")
    qty_kg: float = Field(description="Quantity converted to kilograms. 1 sack (gona/uru) of carrot ~ 50 kg unless stated.")
    grade: Optional[str] = Field(description="Quality grade if stated (e.g. 'A', 'export'), else null.")
    price_lkr_per_kg: Optional[float] = Field(description="Price per kg if the sender named one, else null.")
    price_kind: Optional[PriceKind] = Field(description="For price reporters: 'collector' (farm gate), 'wholesale' (economic centre) or 'retail'. Else null.")


class ParsedMessage(BaseModel):
    """What Gemini returns for any inbound order or harvest message."""
    intent: Intent = Field("order", description=(
        "'order': a new order, harvest offer or price report. 'edit': changes or completes the pending "
        "order given in the context (return only what changes). 'confirm': agrees to the pending order or "
        "offer (yes, ok, go ahead, ow, ஆம்). 'cancel': says no or cancel. 'status': asks about their orders. "
        "'chat': greeting, thanks or anything else with no order in it."))
    role: Role = Field(description="'farmer' if offering harvest, 'buyer' if placing an order, 'reporter' if reporting today's market prices.")
    language: Lang = Field(description="Language the sender wrote or spoke in.")
    sender_name: Optional[str] = Field(description="Business or person name if visible, else null.")
    location: Optional[str] = Field(description="Town or district in English, e.g. 'Nuwara Eliya', 'Colombo 03'.")
    when: Optional[date] = Field(description="Harvest-ready date (farmer) or needed-by date (buyer), ISO format, else null.")
    items: list[Item]
    unclear: list[str] = Field(description="Short English notes for the ops team on anything you guessed. Never shown to the sender.")
    confidence: float = Field(description="0 to 1. Your confidence that the items and quantities are correct.")
    summary_in_sender_language: str = Field(description="One-sentence confirmation of what you understood, in the sender's language.")
    question_in_sender_language: Optional[str] = Field(None, description=(
        "Null unless a fact Govi cannot trade without is missing and cannot be inferred: the crop, the "
        "quantity, or a farmer's town. Then ONE short, plain question in the sender's language asking only "
        "for that. Never ask about dates, role or anything with a default."))


class Listing(BaseModel):
    id: str
    phone: Optional[str] = None
    lang: Lang = "en"
    farmer: str
    location: str
    crop: str
    qty_kg: float
    ready_on: date
    remaining_kg: float


class Order(BaseModel):
    id: str
    phone: Optional[str] = None
    lang: Lang = "en"
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
    handling_lkr: float = 0  # loading, booking and getting the load to the station or stand
    pickup: str = ""  # where the farmer hands the load over
    door_delivery: bool = False  # carrier delivers to the buyer, so no Colombo pickup run
    source: str  # where the number came from; "ESTIMATE" until field-checked


class Match(BaseModel):
    id: str = ""
    status: Literal["proposed", "confirmed", "declined", "cancelled"] = "proposed"
    farmer_ok: bool = False
    buyer_ok: bool = False
    listing_id: str
    order_id: str
    farmer: str
    buyer: str
    crop: str
    qty_kg: float
    lane: Optional[Lane]
    solo_lane: Optional[Lane] = None
    ship_on: Optional[date] = None
    needed_by: Optional[date] = None
    shipment_id: Optional[str] = None
    transport_lkr_per_kg: float
    solo_transport_lkr_per_kg: float = 0
    farmer_gets_lkr_per_kg: float
    buyer_pays_lkr_per_kg: float
    collector_pays_lkr_per_kg: float
    market_retail_lkr_per_kg: float
    note: str = ""  # e.g. "rescue: backup buy" when a missed shipment was covered


class Shipment(BaseModel):
    """Several matched loads from one town riding the same bus, train or lorry."""
    id: str
    origin: str
    dest: str
    ship_on: date
    lane: Lane
    match_ids: list[str]
    farmers: list[str]
    buyers: list[str]
    total_kg: float
    cost_lkr: float
    lkr_per_kg: float
    solo_cost_lkr: float
    saved_lkr: float
    status: ShipStatus = "planned"
    schedule: dict[str, str] = {}  # status -> planned ISO time
    events: list[dict] = []  # {"status", "at", "note"} as each step happens
    ref: str = ""  # carrier booking reference
    rescue: dict = {}  # what happened when this shipment missed its departure
