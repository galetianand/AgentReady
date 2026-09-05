import hashlib
import time
from typing import Tuple

from schemas.mandate import BuyerIntentMandate
from core.database import StockReservationQuote, ProductInventory


class DeterministicPolicyEngine:
    """
    Deterministic financial policy engine.

    The AI/agent may propose or negotiate a transaction,
    but this engine makes the final deterministic decision.

    Possible decisions:
    - ALLOW
    - BLOCK
    - APPROVAL_REQUIRED
    """

    @staticmethod
    def generate_idempotency_key(
        mandate_id: str,
        merchant_id: str,
        quote_id: str,
        total_paise: int
    ) -> str:
        """
        Generates a canonical SHA-256 idempotency key.

        Uses integer paise to avoid floating-point differences.
        """

        payload = (
            f"{mandate_id}:"
            f"{merchant_id}:"
            f"{quote_id}:"
            f"{total_paise}"
        ).encode("utf-8")

        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def validate_transaction(
        mandate: BuyerIntentMandate,
        product: ProductInventory,
        quote: StockReservationQuote,
        current_time: int = None
    ) -> Tuple[str, str, str]:
        """
        Validates a transaction against deterministic rules.

        Returns:
            (
                decision,
                reason_code,
                human_readable_message
            )

        Decisions:
        - ALLOW
        - BLOCK
        - APPROVAL_REQUIRED
        """

        now = (
            current_time
            if current_time is not None
            else int(time.time())
        )

        # --------------------------------------------------
        # 1. MANDATE EXPIRY CHECK
        # --------------------------------------------------

        mandate_expiry = (
            mandate.created_at +
            mandate.expiry_seconds
        )

        if now > mandate_expiry:
            return (
                "BLOCK",
                "MANDATE_EXPIRED",
                (
                    f"Mandate expired at timestamp "
                    f"{mandate_expiry}. Current time: {now}"
                )
            )

        # --------------------------------------------------
        # 2. MERCHANT ALLOWLIST CHECK
        # --------------------------------------------------

        if (
            mandate.allowed_merchants
            and quote.merchant_id
            not in mandate.allowed_merchants
        ):
            return (
                "BLOCK",
                "MERCHANT_NOT_ALLOWED",
                (
                    f"Merchant '{quote.merchant_id}' "
                    f"is not authorized by this mandate."
                )
            )

        # --------------------------------------------------
        # 3. CATEGORY SCOPE CHECK
        # --------------------------------------------------

        if product.category != mandate.category:
            return (
                "BLOCK",
                "CATEGORY_NOT_ALLOWED",
                (
                    f"Product category "
                    f"'{product.category}' does not match "
                    f"authorized category "
                    f"'{mandate.category}'."
                )
            )

        # --------------------------------------------------
        # 4. QUOTE EXPIRY CHECK
        # --------------------------------------------------

        if now > quote.expires_at:
            return (
                "BLOCK",
                "QUOTE_EXPIRED",
                (
                    f"Quote '{quote.quote_id}' expired at "
                    f"{quote.expires_at}. Current time: {now}"
                )
            )

        # --------------------------------------------------
        # 5. QUOTE STATUS CHECK
        # --------------------------------------------------

        if quote.status != "RESERVED":
            return (
                "BLOCK",
                "QUOTE_INACTIVE",
                (
                    f"Quote '{quote.quote_id}' is not active. "
                    f"Current status: {quote.status}"
                )
            )

        # --------------------------------------------------
        # 6. BUDGET CAP CHECK
        # All amounts are integer paise
        # --------------------------------------------------

        if (
            quote.total_amount_paise
            > mandate.max_budget_paise
        ):
            return (
                "BLOCK",
                "BUDGET_EXCEEDED",
                (
                    f"Quote total ₹"
                    f"{quote.total_amount_paise / 100:.2f} "
                    f"exceeds mandate budget cap ₹"
                    f"{mandate.max_budget_paise / 100:.2f}."
                )
            )

        # --------------------------------------------------
        # 7. QUANTITY INTEGRITY CHECK
        # --------------------------------------------------

        if quote.quantity != mandate.target_quantity:
            return (
                "BLOCK",
                "QUANTITY_MISMATCH",
                (
                    f"Quote quantity ({quote.quantity}) "
                    f"does not match authorized quantity "
                    f"({mandate.target_quantity})."
                )
            )

        # --------------------------------------------------
        # 8. FINANCIAL SANITY CHECK
        # --------------------------------------------------

        if (
            quote.unit_price_paise <= 0
            or quote.quantity <= 0
            or quote.total_amount_paise <= 0
        ):
            return (
                "BLOCK",
                "INVALID_VALUE",
                (
                    "Invalid transaction values detected. "
                    "Price, quantity and total must be positive."
                )
            )

        # --------------------------------------------------
        # ALL DETERMINISTIC CHECKS PASSED
        # --------------------------------------------------

        return (
            "ALLOW",
            "PASSED_ALL_GUARDRAILS",
            (
                "Transaction is strictly compliant with "
                "the mandate, quote, inventory and policy rules."
            )
        )