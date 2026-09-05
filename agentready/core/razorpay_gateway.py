import os
import hmac
import hashlib

from typing import Dict, Any

import razorpay


class RazorpayPaymentService:
    """
    Safe payment gateway wrapper.

    - Accepts money only in integer paise.
    - Uses Razorpay TEST MODE when valid credentials are configured.
    - Falls back to an explicitly labelled MOCK_MODE for offline demos.
    - MOCK_MODE never represents a real Razorpay payment.
    """

    def __init__(self):

        self.key_id = os.getenv(
            "RAZORPAY_KEY_ID"
        )

        self.key_secret = os.getenv(
            "RAZORPAY_KEY_SECRET"
        )


        # ---------------------------------------------------------
        # WEBHOOK SECRET
        # ---------------------------------------------------------

        self.webhook_secret = os.getenv(
            "RAZORPAY_WEBHOOK_SECRET",
            "default_secret"
        )

        self.is_mock_mode = not (
            self.key_id
            and self.key_secret
            and self.key_id.startswith(
                "rzp_test_"
            )
        )

        self.client = None

        if not self.is_mock_mode:

            self.client = razorpay.Client(
                auth=(
                    self.key_id,
                    self.key_secret
                )
            )


    # =============================================================
    # WEBHOOK SIGNATURE VERIFICATION
    # =============================================================

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature: str
    ) -> bool:
        """
        Cryptographically verifies that the webhook
        genuinely originated from Razorpay.

        Uses HMAC SHA-256 and constant-time comparison.
        """

        if not raw_body or not signature:
            return False

        expected_signature = hmac.new(
            self.webhook_secret.encode(
                "utf-8"
            ),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(
            expected_signature,
            signature
        )


    # =============================================================
    # CREATE GATED ORDER
    # =============================================================

    def create_gated_order(
        self,
        amount_paise: int,
        receipt_id: str,
        notes: Dict[str, str],
        idempotency_key: str
    ) -> Dict[str, Any]:
        """
        Creates a Razorpay TEST MODE order using integer paise.

        If Razorpay TEST MODE credentials are unavailable, returns a
        clearly labelled MOCK_MODE order for offline demonstration.

        IMPORTANT:
        A MOCK_MODE order is NOT a real Razorpay order and does not
        represent a successful payment.
        """

        # ---------------------------------------------------------
        # HARD SANITY VALIDATION
        # ---------------------------------------------------------

        if not isinstance(
            amount_paise,
            int
        ):
            raise ValueError(
                "Payment amount must be an integer value in paise"
            )

        if amount_paise <= 0:

            raise ValueError(
                "Payment amount must be greater than zero"
            )

        if not idempotency_key:

            raise ValueError(
                "Idempotency key is required"
            )

        # ---------------------------------------------------------
        # COMMON PAYMENT PAYLOAD
        # ---------------------------------------------------------

        payload = {

            "amount": amount_paise,

            "currency": "INR",

            "receipt": str(
                receipt_id
            )[:40],

            "notes": {

                **notes,

                "idempotency_key": (
                    idempotency_key[:40]
                )
            }
        }

        # ---------------------------------------------------------
        # MOCK / OFFLINE DEMO MODE
        # ---------------------------------------------------------

        if self.is_mock_mode:

            mock_order_id = (
                f"order_mock_"
                f"{idempotency_key[:12]}"
            )

            return {

                "id": mock_order_id,

                "entity": "mock_order",

                "amount": amount_paise,

                "currency": "INR",

                "status": "MOCK_CREATED",

                # Explicit truthfulness fields

                "gateway_mode": "MOCK_MODE",

                "is_mock": True,

                "payment_executed": False,

                "message": (
                    "MOCK_MODE: No real Razorpay order "
                    "or payment was created. "
                    "This response exists only for "
                    "offline/demo fallback."
                ),

                "notes": {

                    **payload["notes"],

                    "mode": "MOCK_MODE"
                }
            }

        # ---------------------------------------------------------
        # RAZORPAY TEST MODE
        # ---------------------------------------------------------

        payload["notes"][
            "mode"
        ] = "RAZORPAY_TEST_MODE"

        try:

            order = self.client.order.create(
                data=payload
            )

            # Add application-level mode metadata.
            # This does not claim Razorpay generated these fields.

            order[
                "gateway_mode"
            ] = "RAZORPAY_TEST_MODE"

            order[
                "is_mock"
            ] = False

            order[
                "payment_executed"
            ] = False

            return order

        except Exception as error:

            # IMPORTANT:
            # Do not silently pretend Razorpay succeeded.
            # Return a clearly labelled failure for the application
            # to handle safely.

            return {

                "id": None,

                "entity": "order",

                "status": (
                    "RAZORPAY_TEST_MODE_FAILED"
                ),

                "gateway_mode": (
                    "RAZORPAY_TEST_MODE"
                ),

                "is_mock": False,

                "payment_executed": False,

                "error": str(
                    error
                ),

                "message": (
                    "Razorpay TEST MODE order creation "
                    "failed. No payment was executed."
                )
            }