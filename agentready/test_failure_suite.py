import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi.testclient import TestClient

from schemas.mandate import BuyerIntentMandate

from core.database import (
    SessionLocal,
    TransactionLedger,
    ProductInventory,
    StockReservationQuote,
    seed_database
)

from core.policy_engine import DeterministicPolicyEngine
from agents.merchant_agent import MerchantSalesAgent
from app import app


# =============================================================
# TERMINAL COLORS
# =============================================================

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


# =============================================================
# DISPLAY HELPERS
# =============================================================

def print_header(title: str):

    print(
        f"\n{BOLD}{CYAN}"
        f"{'=' * 70}"
        f"{RESET}"
    )

    print(
        f"{BOLD}{CYAN}"
        f" RUNNING: {title}"
        f"{RESET}"
    )

    print(
        f"{BOLD}{CYAN}"
        f"{'=' * 70}"
        f"{RESET}"
    )


def print_pass(message: str):

    print(
        f" {GREEN}[PASSED]{RESET} {message}"
    )


def print_fail(message: str):

    print(
        f" {RED}[FAILED]{RESET} {message}"
    )


# =============================================================
# HELPER: RESET INVENTORY STATE
# =============================================================

def reset_inventory_state():
    """
    Reset demo inventory to a predictable state.

    This allows inventory-dependent tests to run
    independently without interference from previous tests.
    """

    db = SessionLocal()

    try:

        product = (
            db.query(ProductInventory)
            .filter(
                ProductInventory.product_id
                == "prod_kb_01"
            )
            .first()
        )

        if product:

            product.stock_available = 50

            product.stock_reserved = 0

            product.stock_sold = 0

            product.updated_at = int(time.time())

            db.commit()

    finally:

        db.close()


# =============================================================
# SCENARIO A
# 90% DISCOUNT / MERCHANT MARGIN JAILBREAK
# =============================================================

def test_scenario_a_margin_jailbreak():

    print_header(
        "Scenario A: 90% Discount / Merchant Margin Jailbreak"
    )

    db = SessionLocal()

    seed_database(db)

    reset_inventory_state()

    try:

        agent = MerchantSalesAgent()

        # Retail price = ₹2,800
        # Attacker attempts ₹280 (90% discount)

        lowball_paise = 28000

        result = agent.request_quote(

            db=db,

            mandate_id="mnd_test_jailbreak",

            product_id="prod_kb_01",

            requested_qty=10,

            offered_unit_price_paise=lowball_paise
        )

        print(
            "DEBUG Scenario A Result:",
            result
        )

        # Quote should be created safely
        assert (
            result["status"]
            == "RESERVED"
        ), result

        # Merchant should counter the aggressive lowball bid
        assert (
            result["negotiation_outcome"]
            == "COUNTER_OFFER"
        ), result

        # -----------------------------------------------------
        # MINIMUM SAFE MARGIN FLOOR
        #
        # Cost price = ₹1,900 = 190000 paise
        #
        # Minimum margin = 15%
        #
        # Margin floor:
        # 190000 × 1.15 = 218500 paise
        # -----------------------------------------------------

        minimum_margin_floor = 218500

        assert (

            result["unit_price_paise"]

            >= minimum_margin_floor

        ), (
            f"Counter price: "
            f"{result['unit_price_paise']} paise | "

            f"Expected minimum margin floor: "
            f"{minimum_margin_floor} paise | "

            f"Policy: {agent.policy}"
        )

        # Cleanup reservation

        MerchantSalesAgent.release_reservation(

            db,

            result["quote_id"],

            reason="TEST_CLEANUP"
        )

        print_pass(

            "90% discount jailbreak blocked. "

            f"Safe counter offer: "

            f"₹{result['unit_price_paise'] / 100:.2f}"
        )

    finally:

        db.close()


# =============================================================
# SCENARIO B
# PROMPT INJECTION / BUDGET OVERFLOW
# =============================================================

def test_scenario_b_budget_overflow():

    print_header(
        "Scenario B: Prompt Injection / Budget Overflow"
    )

    mandate = BuyerIntentMandate(

        mandate_id="mnd_attack_budget",

        user_id="usr_attack_01",

        category="PERIPHERALS_KEYBOARDS",

        allowed_merchants=[
            "mer_techgear_01"
        ],

        # ₹25,000 maximum budget

        max_budget_paise=2500000,

        target_quantity=10,

        created_at=int(time.time()),

        expiry_seconds=1800
    )

    product = ProductInventory(

        product_id="prod_kb_01",

        merchant_id="mer_techgear_01",

        name="Mechanical Wireless Keyboard",

        category="PERIPHERALS_KEYBOARDS",

        retail_price_paise=280000,

        cost_price_paise=190000,

        stock_total=50,

        stock_available=50,

        stock_reserved=0,

        stock_sold=0
    )

    # ---------------------------------------------------------
    # ATTACK
    #
    # ₹5,000 per unit × 10
    #
    # Total = ₹50,000
    #
    # Authorized budget = ₹25,000
    # ---------------------------------------------------------

    quote = StockReservationQuote(

        quote_id="qt_injected_attack",

        mandate_id="mnd_attack_budget",

        merchant_id="mer_techgear_01",

        product_id="prod_kb_01",

        quantity=10,

        unit_price_paise=500000,

        total_amount_paise=5000000,

        status="RESERVED",

        created_at=int(time.time()),

        expires_at=int(time.time()) + 60
    )

    decision, reason_code, message = (

        DeterministicPolicyEngine
        .validate_transaction(

            mandate=mandate,

            product=product,

            quote=quote
        )
    )

    assert (
        decision == "BLOCK"
    ), (
        decision,
        reason_code,
        message
    )

    assert (
        reason_code
        == "BUDGET_EXCEEDED"
    ), reason_code

    print_pass(

        "₹50,000 injected transaction blocked by "

        f"Policy Engine: {reason_code}"
    )


# =============================================================
# SCENARIO C
# IDEMPOTENCY / REPLAY SUPPRESSION
# =============================================================

def test_scenario_c_idempotency_replay():

    print_header(
        "Scenario C: Idempotency & Replay Protection"
    )

    reset_inventory_state()

    client = TestClient(app)

    mandate_id = (
        f"mnd_replay_"
        f"{int(time.time() * 1000)}"
    )

    mandate_payload = {

        "mandate_id":
            mandate_id,

        "user_id":
            "usr_judge",

        "category":
            "PERIPHERALS_KEYBOARDS",

        "allowed_merchants": [
            "mer_techgear_01"
        ],

        # ₹25,000

        "max_budget_paise":
            2500000,

        "target_quantity":
            5,

        "created_at":
            int(time.time()),

        "expiry_seconds":
            1800
    }

    endpoint = (

        "/api/v1/agent/transact"

        "?product_id=prod_kb_01"

        "&bid_unit_price_paise=240000"
    )

    # ---------------------------------------------------------
    # FIRST REQUEST
    # ---------------------------------------------------------

    first_response = client.post(

        endpoint,

        json=mandate_payload
    )

    print(
        "\nDEBUG First Response Status:",
        first_response.status_code
    )

    print(
        "DEBUG First Response Body:",
        first_response.text
    )

    assert (
        first_response.status_code == 200
    ), first_response.text

    first_data = first_response.json()

    print(
        "DEBUG First Response Data:",
        first_data
    )

    # ---------------------------------------------------------
    # UPDATED APP.PY SUCCESS STATUSES
    #
    # Razorpay Test Mode:
    # ORDER_CREATED_TEST_MODE
    #
    # Mock fallback:
    # ORDER_CREATED_MOCK_MODE
    # ---------------------------------------------------------

    valid_order_statuses = [

        "ORDER_CREATED_TEST_MODE",

        "ORDER_CREATED_MOCK_MODE"
    ]

    assert (

        first_data["status"]

        in valid_order_statuses

    ), (
        f"Unexpected transaction status: "
        f"{first_data}"
    )

    assert (
        first_data.get("razorpay_order_id")
    ), first_data

    first_order_id = (

        first_data[
            "razorpay_order_id"
        ]
    )

    print_pass(

        f"First order created safely: "

        f"{first_order_id}"
    )

    # ---------------------------------------------------------
    # REPLAY REQUEST
    #
    # Same mandate + same product
    #
    # Must return existing order
    # and must NOT create another charge/order.
    # ---------------------------------------------------------

    replay_response = client.post(

        endpoint,

        json=mandate_payload
    )

    print(
        "\nDEBUG Replay Response Status:",
        replay_response.status_code
    )

    print(
        "DEBUG Replay Response Body:",
        replay_response.text
    )

    assert (
        replay_response.status_code == 200
    ), replay_response.text

    replay_data = replay_response.json()

    assert (

        replay_data["status"]

        == "REPLAY_SUPPRESSED_EXISTING_ORDER"

    ), replay_data

    assert (

        replay_data["razorpay_order_id"]

        == first_order_id

    ), (
        f"First order: {first_order_id} | "

        f"Replay order: "

        f"{replay_data.get('razorpay_order_id')}"
    )

    assert (

        replay_data["audit_trail"]

        .get("is_replay")

        is True

    ), replay_data

    print_pass(

        "Replay transaction suppressed. "

        "Existing order returned without duplicate billing."
    )


# =============================================================
# SCENARIO D
# QUOTE EXPIRY + INVENTORY RELEASE
# =============================================================

def test_scenario_d_quote_expiry_and_release():

    print_header(
        "Scenario D: Quote Expiry & Automatic Stock Release"
    )

    reset_inventory_state()

    db = SessionLocal()

    try:

        agent = MerchantSalesAgent()

        result = agent.request_quote(

            db=db,

            mandate_id="mnd_expiry_test",

            product_id="prod_kb_01",

            requested_qty=5,

            offered_unit_price_paise=240000
        )

        assert (

            result["status"]

            == "RESERVED"

        ), result

        quote_id = result["quote_id"]

        quote = (

            db.query(
                StockReservationQuote
            )

            .filter(

                StockReservationQuote.quote_id

                == quote_id

            )

            .first()
        )

        assert quote is not None

        product = (

            db.query(
                ProductInventory
            )

            .filter(

                ProductInventory.product_id

                == "prod_kb_01"

            )

            .first()
        )

        assert product is not None

        available_after_reservation = (

            product.stock_available
        )

        mandate = BuyerIntentMandate(

            mandate_id="mnd_expiry_test",

            user_id="usr_expiry",

            category="PERIPHERALS_KEYBOARDS",

            allowed_merchants=[
                "mer_techgear_01"
            ],

            max_budget_paise=2500000,

            target_quantity=5,

            created_at=int(time.time()),

            expiry_seconds=1800
        )

        # -----------------------------------------------------
        # Simulate time after quote expiration
        # -----------------------------------------------------

        decision, reason_code, message = (

            DeterministicPolicyEngine
            .validate_transaction(

                mandate=mandate,

                product=product,

                quote=quote,

                current_time=(
                    quote.expires_at + 10
                )
            )
        )

        assert (

            decision == "BLOCK"

        ), (
            decision,
            reason_code,
            message
        )

        assert (

            reason_code

            == "QUOTE_EXPIRED"

        ), reason_code

        # -----------------------------------------------------
        # Release reserved stock
        # -----------------------------------------------------

        released = (

            MerchantSalesAgent
            .release_reservation(

                db,

                quote_id,

                reason="QUOTE_EXPIRED"
            )
        )

        assert (
            released is True
        )

        db.refresh(product)

        assert (

            product.stock_available

            == available_after_reservation + 5

        ), (
            f"Expected available stock: "

            f"{available_after_reservation + 5} | "

            f"Actual: "

            f"{product.stock_available}"
        )

        print_pass(

            "Expired quote blocked with QUOTE_EXPIRED "

            "and reserved inventory returned."
        )

    finally:

        db.close()


# =============================================================
# SCENARIO E
# STOCK EXHAUSTION / OVERSALE PREVENTION
# =============================================================

def test_scenario_e_stock_exhaustion():

    print_header(
        "Scenario E: Stock Exhaustion & Overselling Defense"
    )

    reset_inventory_state()

    db = SessionLocal()

    try:

        agent = MerchantSalesAgent()

        product = (

            db.query(
                ProductInventory
            )

            .filter(

                ProductInventory.product_id

                == "prod_kb_01"

            )

            .first()
        )

        assert product is not None

        available_stock = (

            product.stock_available
        )

        assert (
            available_stock > 0
        )

        # -----------------------------------------------------
        # FIRST BUYER RESERVES ALL AVAILABLE STOCK
        # -----------------------------------------------------

        quote_a = agent.request_quote(

            db=db,

            mandate_id="mnd_stock_a",

            product_id="prod_kb_01",

            requested_qty=available_stock,

            offered_unit_price_paise=240000
        )

        assert (

            quote_a["status"]

            == "RESERVED"

        ), quote_a

        # -----------------------------------------------------
        # SECOND BUYER ATTEMPTS ONE EXTRA UNIT
        # -----------------------------------------------------

        quote_b = agent.request_quote(

            db=db,

            mandate_id="mnd_stock_b",

            product_id="prod_kb_01",

            requested_qty=1,

            offered_unit_price_paise=240000
        )

        assert (

            quote_b["status"]

            == "REJECTED"

        ), quote_b

        assert (

            quote_b["reason"]

            == "STOCK_INSUFFICIENT"

        ), quote_b

        # -----------------------------------------------------
        # CLEANUP
        # -----------------------------------------------------

        MerchantSalesAgent.release_reservation(

            db,

            quote_a["quote_id"],

            reason="TEST_CLEANUP"
        )

        db.refresh(product)

        assert (

            product.stock_available

            == available_stock

        ), (
            f"Expected stock: "

            f"{available_stock} | "

            f"Actual: "

            f"{product.stock_available}"
        )

        print_pass(

            "Overselling prevented. "

            "Second buyer rejected with "

            "STOCK_INSUFFICIENT."
        )

    finally:

        db.close()


# =============================================================
# SCENARIO F
# MANDATE EXPIRY + MERCHANT ALLOWLIST
# =============================================================

def test_scenario_f_mandate_expiry_and_allowlist():

    print_header(
        "Scenario F: Mandate Scope & Merchant Allowlist"
    )

    product = ProductInventory(

        product_id="prod_test_scope",

        merchant_id="mer_unauthorized_store",

        name="Test Keyboard",

        category="PERIPHERALS_KEYBOARDS",

        retail_price_paise=280000,

        cost_price_paise=190000,

        stock_total=50,

        stock_available=50,

        stock_reserved=0,

        stock_sold=0
    )

    quote = StockReservationQuote(

        quote_id="qt_scope_test",

        mandate_id="mnd_scope_test",

        merchant_id="mer_unauthorized_store",

        product_id="prod_test_scope",

        quantity=5,

        unit_price_paise=240000,

        total_amount_paise=1200000,

        status="RESERVED",

        created_at=int(time.time()),

        expires_at=int(time.time()) + 60
    )

    # ---------------------------------------------------------
    # MERCHANT NOT ALLOWED
    # ---------------------------------------------------------

    mandate_bad_merchant = BuyerIntentMandate(

        mandate_id="mnd_bad_merchant",

        user_id="usr_scope",

        category="PERIPHERALS_KEYBOARDS",

        allowed_merchants=[
            "mer_techgear_01"
        ],

        max_budget_paise=2500000,

        target_quantity=5,

        created_at=int(time.time()),

        expiry_seconds=1800
    )

    decision_1, reason_1, _ = (

        DeterministicPolicyEngine
        .validate_transaction(

            mandate=mandate_bad_merchant,

            product=product,

            quote=quote
        )
    )

    assert (
        decision_1 == "BLOCK"
    )

    assert (
        reason_1
        == "MERCHANT_NOT_ALLOWED"
    )

    print_pass(

        f"Unauthorized merchant blocked: "

        f"{reason_1}"
    )

    # ---------------------------------------------------------
    # EXPIRED MANDATE
    # ---------------------------------------------------------

    mandate_expired = BuyerIntentMandate(

        mandate_id="mnd_expired",

        user_id="usr_expired",

        category="PERIPHERALS_KEYBOARDS",

        allowed_merchants=[
            "mer_unauthorized_store"
        ],

        max_budget_paise=2500000,

        target_quantity=5,

        created_at=(
            int(time.time()) - 2000
        ),

        expiry_seconds=1800
    )

    decision_2, reason_2, _ = (

        DeterministicPolicyEngine
        .validate_transaction(

            mandate=mandate_expired,

            product=product,

            quote=quote
        )
    )

    assert (
        decision_2 == "BLOCK"
    )

    assert (
        reason_2
        == "MANDATE_EXPIRED"
    )

    print_pass(

        f"Expired mandate blocked: "

        f"{reason_2}"
    )


# =============================================================
# SCENARIO G
# CATEGORY SCOPE TAMPERING
# =============================================================

def test_scenario_g_category_scope_attack():

    print_header(
        "Scenario G: Category Scope Tampering Defense"
    )

    mandate = BuyerIntentMandate(

        mandate_id="mnd_category_attack",

        user_id="usr_category",

        category="LAPTOPS",

        allowed_merchants=[
            "mer_techgear_01"
        ],

        max_budget_paise=2500000,

        target_quantity=5,

        created_at=int(time.time()),

        expiry_seconds=1800
    )

    product = ProductInventory(

        product_id="prod_keyboard_attack",

        merchant_id="mer_techgear_01",

        name="Keyboard",

        category="PERIPHERALS_KEYBOARDS",

        retail_price_paise=280000,

        cost_price_paise=190000,

        stock_total=50,

        stock_available=50,

        stock_reserved=0,

        stock_sold=0
    )

    quote = StockReservationQuote(

        quote_id="qt_category_attack",

        mandate_id="mnd_category_attack",

        merchant_id="mer_techgear_01",

        product_id="prod_keyboard_attack",

        quantity=5,

        unit_price_paise=240000,

        total_amount_paise=1200000,

        status="RESERVED",

        created_at=int(time.time()),

        expires_at=int(time.time()) + 60
    )

    decision, reason_code, _ = (

        DeterministicPolicyEngine
        .validate_transaction(

            mandate=mandate,

            product=product,

            quote=quote
        )
    )

    assert (
        decision == "BLOCK"
    )

    assert (
        reason_code
        == "CATEGORY_NOT_ALLOWED"
    )

    print_pass(

        "Category tampering attack blocked: "

        f"{reason_code}"
    )

# =============================================================
# SCENARIO H: NATURAL LANGUAGE INTENT PARSER
# =============================================================

def test_llm_natural_language_intent_parser():

    print_header(
        "Scenario H: Natural Language Intent Parser"
    )

    from agents.buyer_agent import AutonomousBuyerAgent

    prompt = (
        "I want to purchase 8 wireless keyboards for my office, "
        "total budget is 20000 rupees."
    )

    mandate = (
        AutonomousBuyerAgent
        .parse_intent_with_llm(prompt)
    )

    assert (
        mandate.target_quantity == 8
    ), (
        f"Expected 8 units, "
        f"got {mandate.target_quantity}"
    )

    assert (
        mandate.max_budget_paise == 2000000
    ), (
        f"Expected 2000000 paise, "
        f"got {mandate.max_budget_paise}"
    )

    assert (
        mandate.category
        == "PERIPHERALS_KEYBOARDS"
    )

    print_pass(
        "Natural language successfully parsed: "
        f"Qty={mandate.target_quantity}, "
        f"Budget=₹{mandate.max_budget_paise / 100:,.2f}"
    )

    # =============================================================
# SCENARIO I
# CRYPTOGRAPHIC WEBHOOK RECONCILIATION
# =============================================================

def test_scenario_i_webhook_reconciliation():

    print_header(
        "Scenario I: Cryptographic Webhook Reconciliation"
    )

    from fastapi.testclient import TestClient
    import hmac
    import hashlib
    import json

    client = TestClient(app)

    test_order_id = "order_sim_webhook_123"

    webhook_secret = os.getenv(
        "RAZORPAY_WEBHOOK_SECRET",
        "default_secret"
    )

    # ---------------------------------------------------------
    # CREATE TEST TRANSACTION IN LEDGER
    # ---------------------------------------------------------

    db = SessionLocal()

    try:

        # Remove previous test transaction if it exists
        existing = (
            db.query(TransactionLedger)
            .filter(
                TransactionLedger.razorpay_order_id
                == test_order_id
            )
            .first()
        )

        if existing:

            db.delete(existing)

            db.commit()

        # Create an ORDER_CREATED transaction
        test_transaction = TransactionLedger(

            mandate_id="mnd_webhook_test",

            merchant_id="mer_techgear_01",

            product_id="prod_kb_01",

            quote_id="qt_webhook_test",

            idempotency_key=(
                "webhook_test_idempotency_key_123"
            ),

            quantity=1,

            unit_price_paise=240000,

            total_amount_paise=240000,

            razorpay_order_id=test_order_id,

            status="ORDER_CREATED"
        )

        db.add(
            test_transaction
        )

        db.commit()

    finally:

        db.close()

    # ---------------------------------------------------------
    # CREATE RAZORPAY WEBHOOK PAYLOAD
    # ---------------------------------------------------------

    webhook_payload = {

        "event": "order.paid",

        "payload": {

            "order": {

                "entity": {

                    "id": test_order_id

                }

            }

        }

    }

    # IMPORTANT:
    # Use compact JSON so the signed bytes are exactly
    # the same bytes sent in the HTTP request.

    raw_body = json.dumps(
        webhook_payload,
        separators=(",", ":")
    ).encode(
        "utf-8"
    )

    # ---------------------------------------------------------
    # GENERATE VALID HMAC SHA-256 SIGNATURE
    # ---------------------------------------------------------

    signature = hmac.new(

        webhook_secret.encode(
            "utf-8"
        ),

        raw_body,

        hashlib.sha256

    ).hexdigest()

    # ---------------------------------------------------------
    # SEND SIGNED WEBHOOK
    # ---------------------------------------------------------

    response = client.post(

        "/api/v1/webhooks/razorpay",

        content=raw_body,

        headers={

            "x-razorpay-signature":
            signature,

            "content-type":
            "application/json"

        }

    )

    # ---------------------------------------------------------
    # VERIFY HTTP RESPONSE
    # ---------------------------------------------------------

    assert (

        response.status_code == 200

    ), response.text


    # ---------------------------------------------------------
    # VERIFY LEDGER WAS ACTUALLY UPDATED
    # ---------------------------------------------------------

    db = SessionLocal()

    try:

        settled_transaction = (

            db.query(
                TransactionLedger
            )

            .filter(

                TransactionLedger
                .razorpay_order_id
                == test_order_id

            )

            .first()

        )

        assert (

            settled_transaction
            is not None

        )

        assert (

            settled_transaction.status
            == "SETTLED"

        ), (

            f"Expected SETTLED but got "
            f"{settled_transaction.status}"
        )

    finally:

        db.close()


    print_pass(

        "Webhook signature verified via "
        "HMAC SHA-256 and transaction "
        "ledger reconciled to SETTLED."

    )
# =============================================================
# MAIN RUNNER
# =============================================================

if __name__ == "__main__":

    print(

        f"\n{BOLD}{YELLOW}"

        f"{'=' * 70}"

        f"{RESET}"
    )

    print(

        f"{BOLD}{YELLOW}"

        " AGENTREADY RED TEAM FAILURE & SECURITY TEST SUITE "

        f"{RESET}"
    )

    print(

        f"{BOLD}{YELLOW}"

        f"{'=' * 70}"

        f"{RESET}"
    )

    tests = [

        test_scenario_a_margin_jailbreak,

        test_scenario_b_budget_overflow,

        test_scenario_c_idempotency_replay,

        test_scenario_d_quote_expiry_and_release,

        test_scenario_e_stock_exhaustion,

        test_scenario_f_mandate_expiry_and_allowlist,

        test_scenario_g_category_scope_attack,
        test_llm_natural_language_intent_parser,
        test_scenario_i_webhook_reconciliation
    ]

    passed = 0

    failed = 0

    for test in tests:

        try:

            test()

            passed += 1

        except AssertionError as error:

            failed += 1

            print_fail(

                f"{test.__name__}: "

                f"{error}"
            )

        except Exception as error:

            failed += 1

            print_fail(

                f"{test.__name__}: "

                f"Unexpected error: {error}"
            )

    # =========================================================
    # FINAL RESULT
    # =========================================================

    print(

        f"\n{BOLD}{YELLOW}"

        f"{'=' * 70}"

        f"{RESET}"
    )

    print(

        f"{BOLD}"

        f" TEST RESULTS: "

        f"{GREEN}{passed} PASSED{RESET}"

        f" | "

        f"{RED}{failed} FAILED"

        f"{RESET}"
    )

    print(

        f"{BOLD}{YELLOW}"

        f"{'=' * 70}"

        f"{RESET}"
    )

    if failed == 0:

        print(

            f"\n{BOLD}{GREEN}"

            f" ALL {passed} SECURITY & AI AGENT TESTS PASSED! "

            f"{RESET}\n"
        )

    else:

        print(

            f"\n{BOLD}{RED}"

            " SOME TESTS FAILED. REVIEW THE OUTPUT ABOVE. "

            f"{RESET}\n"
        )