import time
import secrets

from typing import List, Optional

from pydantic import BaseModel, Field


class BuyerIntentMandate(BaseModel):
    """
    Typed and scoped purchase authorization.

    All money values are stored in integer paise.
    Example:
        ₹25,000.00 = 2,500,000 paise
    """

    mandate_id: str
    user_id: str

    # Product / transaction scope
    category: str

    # Empty list means any merchant is allowed for this demo.
    allowed_merchants: List[str] = Field(default_factory=list)

    # Financial boundary — integer paise only
    max_budget_paise: int = Field(
        ...,
        gt=0,
        description="Maximum authorized spending amount in integer paise"
    )

    # Quantity boundary
    target_quantity: int = Field(
        ...,
        gt=0,
        description="Maximum authorized quantity"
    )

    # Creation and expiry
    created_at: int = Field(
        default_factory=lambda: int(time.time())
    )

    expiry_seconds: int = Field(
        default=1800,
        gt=0,
        description="Mandate validity duration in seconds"
    )

    # Unique nonce for mandate scope
    nonce: str = Field(
        default_factory=lambda: secrets.token_hex(16)
    )

    # Approval policy
    approval_required_above_paise: Optional[int] = Field(
        default=None,
        gt=0,
        description=(
            "Optional threshold above which explicit approval "
            "is required"
        )
    )

    def is_expired(self) -> bool:
        """Returns True if the mandate has expired."""

        return int(time.time()) > (
            self.created_at + self.expiry_seconds
        )

    def expires_at(self) -> int:
        """Returns the Unix timestamp when the mandate expires."""

        return self.created_at + self.expiry_seconds