from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class ProductListing(BaseModel):
    """
    Machine-readable product listing.

    IMPORTANT:
    All monetary values are stored internally as integer paise.
    Example:
        ₹2,800.00 = 280000 paise
    """

    product_id: str
    name: str
    category: str

    retail_price_paise: int = Field(
        ...,
        ge=0,
        description="Retail price in integer paise. Example: ₹2,800.00 = 280000"
    )

    cost_price_paise: int = Field(
        ...,
        ge=0,
        description="Cost price in integer paise. Example: ₹1,900.00 = 190000"
    )

    stock_total: int = Field(..., ge=0)
    stock_available: int = Field(..., ge=0)
    stock_reserved: int = Field(default=0, ge=0)
    stock_sold: int = Field(default=0, ge=0)


class NegotiationPolicy(BaseModel):
    """
    Hard deterministic merchant negotiation rules.
    """

    enabled: bool = True

    min_margin_pct: float = Field(
        default=15.0,
        ge=0,
        le=100,
        description="Hard minimum merchant margin percentage"
    )

    max_discount_pct: float = Field(
        default=18.0,
        ge=0,
        le=100,
        description="Maximum discount allowed from retail price"
    )

    bulk_threshold_qty: int = Field(
        default=5,
        ge=1,
        description="Minimum quantity required for bulk negotiation"
    )

    quote_ttl_seconds: int = Field(
        default=60,
        ge=1,
        description="Temporary quote and stock reservation validity"
    )


class MerchantCapabilities(BaseModel):
    """
    Explicit machine-readable capabilities supported by this demo merchant.
    """

    catalog_search: bool = True
    stock_check: bool = True
    quote_request: bool = True
    negotiation: bool = True
    order_creation: bool = True
    payment_execution: bool = True


class ShippingTerms(BaseModel):
    """
    Demo merchant shipping and return terms.
    """

    shipping_supported: bool = True
    shipping_fee_paise: int = Field(
        default=0,
        ge=0,
        description="Shipping fee in integer paise"
    )

    estimated_delivery_days: int = Field(
        default=3,
        ge=0
    )

    return_window_days: int = Field(
        default=7,
        ge=0
    )


class MerchantPassport(BaseModel):
    """
    AgentReady Merchant AI Passport.

    This is a DEMO application passport.
    It does NOT claim official verification by Razorpay, NPCI,
    GST, UAP, or any external authority.
    """

    passport_version: str = "1.1.0"

    merchant_id: str
    name: str

    trust_score: float = Field(
        ...,
        ge=0,
        le=100
    )

    # Truthful verification label for Buildathon demo
    verification_status: str = (
        "DEMO_SELF_ASSERTED_NOT_OFFICIALLY_VERIFIED"
    )

    is_demo_verified: bool = True

    capabilities: MerchantCapabilities = Field(
        default_factory=MerchantCapabilities
    )

    catalog: List[ProductListing]

    negotiation_policy: NegotiationPolicy

    shipping_terms: ShippingTerms = Field(
        default_factory=ShippingTerms
    )

    inventory_freshness_timestamp: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    payment_rails: List[str] = Field(
        default_factory=lambda: [
            "RAZORPAY_TEST_MODE",
            "MOCK_GATEWAY_DEMO_ONLY"
        ]
    )

    signing_info: str = (
        "DEMO_ONLY_UNVERIFIED_PASSPORT_NO_OFFICIAL_EXTERNAL_SIGNATURE"
    )