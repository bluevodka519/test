"""Input (data file) and output (API) models.

Money is a Decimal everywhere and is serialised to JSON as a string
(e.g. "159.09") so the frontend never does float arithmetic on it.
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------- input: data files ----------

class Address(BaseModel):
    street: str
    suburb: str
    state: str
    postcode: str


class OrderIn(BaseModel):
    order_no: str
    order_date: str
    status: str
    company: str = ""
    customer: str
    phone: str = ""
    email: str = ""
    address: Address
    is_test: bool = False
    test_note: str = ""


class OrderLineIn(BaseModel):
    sku: str
    quantity: Any  # validated per line so one bad value never breaks the order
    tracking_ref: str
    order_no: str


class Carrier(str, Enum):
    AUSPOST = "AUSPOST"
    STARTRACK = "STARTRACK"
    TNT = "TNT"


class ShipmentIn(BaseModel):
    tracking_ref: str
    tracking_no: str
    carrier: Carrier
    logistics_company: str = ""


# ---------- output: API ----------

class LineStatus(str, Enum):
    OK = "OK"
    SKU_NOT_FOUND = "SKU_NOT_FOUND"
    INVALID_QTY = "INVALID_QTY"
    BAD_PRODUCT_DATA = "BAD_PRODUCT_DATA"


class LineResult(BaseModel):
    position: int  # 1-based within the order, used for "Product N" placeholders
    sku: str
    name: Optional[str] = None
    description: Optional[str] = None
    quantity: Any
    rrp: Optional[Decimal] = None                  # SKU price incl. GST
    unit_price_ex_gst: Optional[Decimal] = None    # RRP / 1.10, rounded for display
    line_subtotal_ex_gst: Optional[Decimal] = None  # ex-GST unit price x quantity, rounded for display
    status: LineStatus
    message: str = ""
    image_url: Optional[str] = None
    tracking_ref: str


class TrackingStatus(str, Enum):
    OK = "OK"
    NO_DATA = "NO_DATA"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    NOT_REQUESTED = "NOT_REQUESTED"


class TrackingEvent(BaseModel):
    date: Optional[str] = None
    description: str = ""
    location: Optional[str] = None


class TrackingResult(BaseModel):
    status: TrackingStatus
    carrier: Optional[str] = None
    tracking_no: Optional[str] = None
    current_status: Optional[str] = None
    last_update: Optional[str] = None
    events: list[TrackingEvent] = Field(default_factory=list)
    message: str = ""


class FeeSource(str, Enum):
    COURIER_QUOTE = "COURIER_QUOTE"
    FORMULA_ESTIMATE = "FORMULA_ESTIMATE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NO_ITEMS = "NO_ITEMS"


class Parcel(BaseModel):
    weight_kg: Decimal
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal
    cubic_kg: Decimal
    item_count: int


class Fee(BaseModel):
    amount: Decimal
    source: FeeSource
    note: str = ""
    zone: Optional[str] = None
    chargeable_kg: Optional[Decimal] = None
    parcel: Optional[Parcel] = None


class ShipmentResult(BaseModel):
    tracking_ref: str
    tracking_no: Optional[str] = None
    carrier: Optional[str] = None
    logistics_company: Optional[str] = None
    lines: list[LineResult]
    tracking: TrackingResult
    fee: Fee


class Totals(BaseModel):
    subtotal_ex_gst: Decimal
    gst: Decimal
    shipment_fee: Decimal
    total: Decimal


class OrderDetail(BaseModel):
    order: OrderIn
    shipments: list[ShipmentResult]
    totals: Totals
    warnings: list[str]


class OrderSummary(BaseModel):
    order_no: str
    order_date: str
    status: str
    customer: str
    company: str
    is_test: bool
    line_count: int
    total: Decimal
    warning_count: int
