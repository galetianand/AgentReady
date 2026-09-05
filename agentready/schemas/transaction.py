from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class QuoteResponse(BaseModel):

    quote_id: str

    merchant_id: str

    product_id: str

    quantity: int

    unit_price_paise: int

    total_amount_paise: int

    free_shipping: bool

    status: str  # RESERVED, EXPIRED, RELEASED, CONSUMED, REJECTED

    created_at: int

    expires_at: int

    reason: Optional[str] = None


class TransactionResponse(BaseModel):

    status: str

    decision: str  # ALLOW, BLOCK, APPROVAL_REQUIRED

    reason_code: str

    razorpay_order_id: Optional[str] = None

    amount_paise: int

    negotiated_savings_paise: int

    # Optional merchant cross-sell / upsell recommendation
    cross_sell_offer: Optional[Dict[str, Any]] = None

    audit_trail: Dict[str, Any]


class AuditTimelineEvent(BaseModel):

    timestamp: int

    actor: str

    event_type: str

    status: str

    details: Dict[str, Any]


class AuditLedgerResponse(BaseModel):

    mandate_id: str

    transaction_status: str

    total_events: int

    timeline: List[AuditTimelineEvent]