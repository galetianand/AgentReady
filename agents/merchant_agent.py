import time
import uuid

from sqlalchemy.orm import Session

from schemas.passport import NegotiationPolicy
from core.database import ProductInventory, StockReservationQuote
from core.audit_service import AuditService


# =============================================================
# MERCHANT SALES AGENT
# =============================================================

class MerchantSalesAgent:

    def __init__(
        self,
        policy: NegotiationPolicy = None
    ):

        self.policy = policy or NegotiationPolicy()


    # =========================================================
    # REQUEST QUOTE
    # =========================================================

    def request_quote(
        self,
        db: Session,
        mandate_id: str,
        product_id: str,
        requested_qty: int,
        offered_unit_price_paise: int
    ) -> dict:

        # -----------------------------------------------
        # 1. FIND PRODUCT
        # -----------------------------------------------

        product = (
            db.query(ProductInventory)
            .filter(
                ProductInventory.product_id == product_id
            )
            .first()
        )

        if not product:
            return {
                "status": "REJECTED",
                "reason": "PRODUCT_NOT_FOUND"
            }


        # -----------------------------------------------
        # 2. INVENTORY VALIDATION
        # -----------------------------------------------

        if requested_qty <= 0:

            return {
                "status": "REJECTED",
                "reason": "INVALID_QUANTITY"
            }


        if product.stock_available < requested_qty:

            AuditService.log_event(
                db,
                mandate_id,
                "STOCK_INSUFFICIENT",
                "MERCHANT_AGENT",
                "FAILED",
                {
                    "product_id": product_id,
                    "requested": requested_qty,
                    "available": product.stock_available
                }
            )

            return {
                "status": "REJECTED",
                "reason": "STOCK_INSUFFICIENT",
                "available_stock": product.stock_available
            }


        # -----------------------------------------------
        # 3. DETERMINISTIC MERCHANT MARGIN FLOOR
        # -----------------------------------------------

        min_margin_paise = int(
            product.cost_price_paise
            * (
                1.0
                + (
                    self.policy.min_margin_pct
                    / 100.0
                )
            )
        )


        # -----------------------------------------------
        # 4. DISCOUNT POLICY
        # -----------------------------------------------

        is_bulk = (
            requested_qty
            >= self.policy.bulk_threshold_qty
        )

        max_discount = (
            self.policy.max_discount_pct / 100.0
            if is_bulk
            else 0.05
        )

        discount_floor_paise = int(
            product.retail_price_paise
            * (
                1.0 - max_discount
            )
        )

        # Final merchant floor:
        # Must satisfy BOTH margin and discount rules.
        target_floor_paise = max(
            min_margin_paise,
            discount_floor_paise
        )


        # -----------------------------------------------
        # 5. NEGOTIATION OUTCOME
        # -----------------------------------------------

        if (
            offered_unit_price_paise
            >= product.retail_price_paise
        ):

            final_unit_price_paise = (
                product.retail_price_paise
            )

            outcome = "ACCEPTED"

        elif (
            offered_unit_price_paise
            >= target_floor_paise
        ):

            final_unit_price_paise = (
                offered_unit_price_paise
            )

            outcome = "ACCEPTED"

        else:

            final_unit_price_paise = (
                target_floor_paise
            )

            outcome = "COUNTER_OFFER"


        # -----------------------------------------------
        # 6. CALCULATE TOTAL
        # All financial values remain integer paise.
        # -----------------------------------------------

        total_amount_paise = (
            final_unit_price_paise
            * requested_qty
        )


        # -----------------------------------------------
        # 7. ATOMIC-LIKE INVENTORY STATE TRANSITION
        #
        # Available -> Reserved
        # -----------------------------------------------

        product.stock_available -= requested_qty
        product.stock_reserved += requested_qty


        # -----------------------------------------------
        # 8. CREATE TIME-LOCKED QUOTE
        # -----------------------------------------------

        now = int(time.time())

        quote_id = (
            f"qt_{uuid.uuid4().hex[:10]}"
        )

        quote = StockReservationQuote(

            quote_id=quote_id,

            mandate_id=mandate_id,

            merchant_id=product.merchant_id,

            product_id=product_id,

            quantity=requested_qty,

            unit_price_paise=(
                final_unit_price_paise
            ),

            total_amount_paise=(
                total_amount_paise
            ),

            status="RESERVED",

            created_at=now,

            expires_at=(
                now
                + self.policy.quote_ttl_seconds
            )
        )

        db.add(quote)

        db.commit()


        # -----------------------------------------------
        # 9. AUDIT LOG
        # -----------------------------------------------

        AuditService.log_event(

            db,

            mandate_id,

            "STOCK_RESERVED",

            "MERCHANT_AGENT",

            "SUCCESS",

            {

                "quote_id": quote_id,

                "product_id": product_id,

                "quantity": requested_qty,

                "negotiation_outcome": outcome,

                "stock_available_after":
                    product.stock_available,

                "stock_reserved_after":
                    product.stock_reserved
            },

            quote_id=quote_id
        )


        # =================================================
        # 10. DYNAMIC CROSS-SELL RECOMMENDATION ENGINE
        # =================================================

        cross_sell = None

        # Keyboard purchase -> recommend complementary desk mat
        if product_id == "prod_kb_01":

            addon = (
                db.query(ProductInventory)
                .filter(
                    ProductInventory.product_id
                    == "prod_mp_01"
                )
                .first()
            )

            # Only offer if sufficient inventory exists
            if (
                addon
                and addon.stock_available >= requested_qty
            ):

                # -------------------------------------------------
                # MARGIN-SAFE BUNDLE PRICE
                #
                # Gemini suggested 40% discount directly.
                # We additionally ensure the merchant does not
                # sell below the configured minimum margin floor.
                # -------------------------------------------------

                discounted_bundle_price_paise = int(
                    addon.retail_price_paise * 0.60
                )

                addon_min_margin_price_paise = int(
                    addon.cost_price_paise
                    * (
                        1.0
                        + (
                            self.policy.min_margin_pct
                            / 100.0
                        )
                    )
                )

                bundle_price_paise = max(
                    discounted_bundle_price_paise,
                    addon_min_margin_price_paise
                )

                discount_percent = int(
                    (
                        1
                        - (
                            bundle_price_paise
                            / addon.retail_price_paise
                        )
                    )
                    * 100
                )

                cross_sell = {

                    "product_id":
                        addon.product_id,

                    "name":
                        addon.name,

                    "category":
                        addon.category,

                    "quantity_available":
                        addon.stock_available,

                    "requested_quantity":
                        requested_qty,

                    "retail_price_paise":
                        addon.retail_price_paise,

                    "bundle_price_paise":
                        bundle_price_paise,

                    "discount_percent":
                        discount_percent,

                    "pitch": (
                        f"Complete your workspace: "
                        f"Add {requested_qty}x "
                        f"'{addon.name}' for just "
                        f"₹{bundle_price_paise / 100:,.2f} each "
                        f"({discount_percent}% OFF)."
                    )
                }


        # -----------------------------------------------
        # FINAL QUOTE RESPONSE
        # -----------------------------------------------

        return {

            "status": "RESERVED",

            "negotiation_outcome": outcome,

            "quote_id": quote_id,

            "merchant_id":
                product.merchant_id,

            "product_id":
                product_id,

            "quantity":
                requested_qty,

            "unit_price_paise":
                final_unit_price_paise,

            "total_amount_paise":
                total_amount_paise,

            "free_shipping":
                is_bulk,

            # Dynamic merchant-side upsell offer
            "cross_sell_offer":
                cross_sell,

            "created_at":
                now,

            "expires_at":
                quote.expires_at
        }


    # ===================================================
    # RELEASE RESERVATION
    # ===================================================

    @staticmethod
    def release_reservation(
        db: Session,
        quote_id: str,
        reason: str = "RELEASED"
    ):
        """
        Idempotently releases reserved inventory.

        Reserved -> Available
        """

        quote = (
            db.query(StockReservationQuote)
            .filter(
                StockReservationQuote.quote_id
                == quote_id
            )
            .first()
        )

        if (
            not quote
            or quote.status != "RESERVED"
        ):
            return False

        product = (
            db.query(ProductInventory)
            .filter(
                ProductInventory.product_id
                == quote.product_id
            )
            .first()
        )

        if product:

            product.stock_reserved = max(
                0,
                product.stock_reserved
                - quote.quantity
            )

            product.stock_available += (
                quote.quantity
            )

        quote.status = reason

        db.commit()

        AuditService.log_event(

            db,

            "SYSTEM",

            "STOCK_RELEASED",

            "MERCHANT_AGENT",

            "SUCCESS",

            {

                "quote_id":
                    quote_id,

                "product_id":
                    quote.product_id,

                "quantity_returned":
                    quote.quantity,

                "reason":
                    reason,

                "stock_available_after":

                    product.stock_available

                    if product

                    else 0
            },

            quote_id=quote_id
        )

        return True


    # ===================================================
    # CONSUME RESERVATION
    # ===================================================

    @staticmethod
    def consume_reservation(
        db: Session,
        quote_id: str
    ):
        """
        Converts reserved inventory to sold inventory.

        Reserved -> Sold
        """

        quote = (
            db.query(StockReservationQuote)
            .filter(
                StockReservationQuote.quote_id
                == quote_id
            )
            .first()
        )

        if (
            not quote
            or quote.status != "RESERVED"
        ):
            return False

        product = (
            db.query(ProductInventory)
            .filter(
                ProductInventory.product_id
                == quote.product_id
            )
            .first()
        )

        if product:

            product.stock_reserved = max(
                0,
                product.stock_reserved
                - quote.quantity
            )

            product.stock_sold += (
                quote.quantity
            )

        quote.status = "CONSUMED"

        db.commit()

        AuditService.log_event(

            db,

            "SYSTEM",

            "STOCK_SOLD",

            "MERCHANT_AGENT",

            "SUCCESS",

            {

                "quote_id":
                    quote_id,

                "product_id":
                    quote.product_id,

                "quantity_sold":
                    quote.quantity,

                "stock_sold_total":

                    product.stock_sold

                    if product

                    else 0
            },

            quote_id=quote_id
        )

        return True