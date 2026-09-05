import time
import requests
import pandas as pd
import streamlit as st


# =============================================================
# PAGE CONFIGURATION
# =============================================================

st.set_page_config(
    page_title="AgentReady — Autonomous Commerce",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


API_BASE = "http://127.0.0.1:8000"


# =============================================================
# CUSTOM UI
# =============================================================

st.markdown(
    """
    <style>

    .main {
        background-color: #0e1117;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    div[data-testid="stMetric"] {
        background-color: #171b26;
        border: 1px solid #2b3242;
        padding: 15px;
        border-radius: 12px;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 14px;
    }

    div[data-testid="stMetricValue"] {
        font-size: 25px;
    }

    .section-card {
        background-color: #171b26;
        border: 1px solid #2b3242;
        padding: 18px;
        border-radius: 14px;
        margin-bottom: 12px;
    }

    .hero-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0px;
    }

    .hero-subtitle {
        color: #9aa4b2;
        font-size: 17px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =============================================================
# SESSION STATE INITIALIZATION
# =============================================================

def generate_mandate_id():
    """
    Generate a sufficiently unique demo mandate ID.

    Milliseconds are used so rapid button presses
    do not normally generate the same ID.
    """

    return f"mnd_{int(time.time() * 1000)}"


# -------------------------------------------------------------
# MANDATE STATE
# -------------------------------------------------------------

if "mandate_id_value" not in st.session_state:

    new_id = generate_mandate_id()

    st.session_state["mandate_id_value"] = new_id
    st.session_state["mandate_input"] = new_id


# -------------------------------------------------------------
# AUDIT STATE
# -------------------------------------------------------------

if "audit_mandate_value" not in st.session_state:

    st.session_state["audit_mandate_value"] = (
        st.session_state["mandate_id_value"]
    )

    st.session_state["audit_mandate_input"] = (
        st.session_state["mandate_id_value"]
    )


# -------------------------------------------------------------
# OTHER SESSION STATE
# -------------------------------------------------------------

if "passport" not in st.session_state:
    st.session_state["passport"] = None


if "latest_response" not in st.session_state:
    st.session_state["latest_response"] = None


if "audit_trail" not in st.session_state:
    st.session_state["audit_trail"] = None


if "attack_mode" not in st.session_state:
    st.session_state["attack_mode"] = None


if "last_successful_mandate" not in st.session_state:
    st.session_state["last_successful_mandate"] = None


if "last_successful_bid_paise" not in st.session_state:
    st.session_state["last_successful_bid_paise"] = None


if "last_successful_quantity" not in st.session_state:
    st.session_state["last_successful_quantity"] = None

# -------------------------------------------------------------
# NATURAL LANGUAGE INTENT STATE
# -------------------------------------------------------------

if "parsed_mandate" not in st.session_state:
    st.session_state["parsed_mandate"] = None

if "intent_parse_message" not in st.session_state:
    st.session_state["intent_parse_message"] = None


# =============================================================
# HELPER FUNCTIONS
# =============================================================

def paise_to_inr(paise):

    if paise is None:
        return "₹0.00"

    try:
        return f"₹{int(paise) / 100:,.2f}"

    except Exception:
        return "₹0.00"


def get_json_response(response):

    try:
        return response.json()

    except Exception:

        return {
            "detail": response.text
        }


# =============================================================
# API HEALTH CHECK
# =============================================================

def check_backend():

    try:

        response = requests.get(
            f"{API_BASE}/docs",
            timeout=3
        )

        return response.status_code < 500

    except Exception:

        return False


# =============================================================
# FETCH PASSPORT
# =============================================================

def fetch_passport():

    try:

        response = requests.get(
            f"{API_BASE}/.well-known/ai-passport.json",
            timeout=10
        )

        if response.status_code == 200:

            data = get_json_response(response)

            st.session_state["passport"] = data

            return True, data

        return False, {
            "error": (
                f"HTTP {response.status_code}: "
                f"{response.text}"
            )
        }

    except Exception as e:

        return False, {
            "error": str(e)
        }


# =============================================================
# FETCH AUDIT TRAIL
# =============================================================

def fetch_audit_trail(mandate_id):

    try:

        response = requests.get(
            f"{API_BASE}/api/v1/audit/{mandate_id}",
            timeout=10
        )

        data = get_json_response(response)

        if response.status_code == 200:

            st.session_state["audit_trail"] = data

            return True, data

        return False, data

    except Exception as e:

        return False, {
            "error": str(e)
        }


# =============================================================
# SESSION STATE CALLBACKS
#
# IMPORTANT:
# These callbacks run before widgets are rendered again.
# This prevents StreamlitAPIException.
# =============================================================

def start_new_mandate():

    new_mandate = generate_mandate_id()

    # Update internal values
    st.session_state["mandate_id_value"] = new_mandate
    st.session_state["audit_mandate_value"] = new_mandate

    # Update widget values BEFORE widgets are instantiated
    st.session_state["mandate_input"] = new_mandate
    st.session_state["audit_mandate_input"] = new_mandate

    # Clear transaction state
    st.session_state["attack_mode"] = None
    st.session_state["latest_response"] = None
    st.session_state["audit_trail"] = None
    st.session_state["parsed_mandate"] = None
    st.session_state["intent_parse_message"] = None


def arm_budget_attack():

    st.session_state["attack_mode"] = "budget"


def arm_quantity_attack():

    st.session_state["attack_mode"] = "quantity"


def arm_replay_attack():

    previous_mandate = (
        st.session_state.get(
            "last_successful_mandate"
        )
    )

    if previous_mandate:

        st.session_state["attack_mode"] = "replay"

        # Safe because callback executes before widgets
        st.session_state["mandate_id_value"] = (
            previous_mandate
        )

        st.session_state["audit_mandate_value"] = (
            previous_mandate
        )

        st.session_state["mandate_input"] = (
            previous_mandate
        )

        st.session_state["audit_mandate_input"] = (
            previous_mandate
        )


def clear_attack_mode():

    st.session_state["attack_mode"] = None


# =============================================================
# HEADER
# =============================================================

backend_online = check_backend()


st.markdown(
    """
    <div class="hero-title">
        🛡️ AgentReady
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="hero-subtitle">
        Policy-Governed Agent-to-Agent Commerce Gateway
    </div>
    """,
    unsafe_allow_html=True
)

st.caption(
    "Razorpay AI Buildathon 2026 • "
    "Track 1: AI Growth & Agentic Commerce"
)


# =============================================================
# STATUS BAR
# =============================================================

status_col_1, status_col_2, status_col_3 = st.columns(
    [1, 1, 2]
)

with status_col_1:

    if backend_online:

        st.success(
            "🟢 Backend Online"
        )

    else:

        st.error(
            "🔴 Backend Offline"
        )


with status_col_2:

    st.info(
        "🧪 Demo / Test Mode"
    )


with status_col_3:

    st.caption(
        "AI can discover and negotiate. "
        "The deterministic Payment Trust Engine "
        "has final authority over transaction execution."
    )


st.divider()


# =============================================================
# MAIN THREE COLUMN LAYOUT
# =============================================================

col_passport, col_transaction, col_audit = st.columns(
    [1.1, 1.4, 1.2],
    gap="large"
)


# =============================================================
# COLUMN 1
# MERCHANT AI PASSPORT
# =============================================================

with col_passport:

    st.subheader(
        "🪪 Merchant AI Passport"
    )

    st.caption(
        "Machine-readable merchant identity, "
        "catalog, policy and live inventory."
    )


    # ---------------------------------------------------------
    # FETCH BUTTON
    # ---------------------------------------------------------

    if st.button(
        "🔄 Fetch Merchant Passport",
        use_container_width=True,
        key="fetch_passport_button"
    ):

        with st.spinner(
            "Fetching live merchant state..."
        ):

            success, data = fetch_passport()

            if success:

                st.success(
                    "Merchant passport loaded."
                )

            else:

                st.error(
                    data.get(
                        "error",
                        "Failed to fetch passport."
                    )
                )


    passport = st.session_state.get(
        "passport"
    )


    # ---------------------------------------------------------
    # DISPLAY PASSPORT
    # ---------------------------------------------------------

    if passport:

        merchant_name = passport.get(
            "name",
            "Unknown Merchant"
        )

        merchant_id = passport.get(
            "merchant_id",
            "N/A"
        )

        trust_score = passport.get(
            "trust_score",
            0
        )

        return_window = passport.get(
            "return_window_days",
            0
        )


        st.markdown(
            f"""
            <div class="section-card">
                <h4 style="margin-bottom:5px;">
                    {merchant_name}
                </h4>
                <p style="color:#9aa4b2;">
                    Merchant ID: {merchant_id}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )


        metric_1, metric_2 = st.columns(2)

        metric_1.metric(
            "Trust Score",
            f"{trust_score}/100"
        )

        metric_2.metric(
            "Returns",
            f"{return_window} Days"
        )


        # -----------------------------------------------------
        # PAYMENT RAILS
        # -----------------------------------------------------

        rails = passport.get(
            "payment_rails",
            []
        )

        if rails:

            st.markdown(
                "#### 💳 Payment Capability"
            )

            for rail in rails:

                if rail == "RAZORPAY_TEST_MODE":

                    st.success(
                        "Razorpay TEST MODE"
                    )

                elif rail == "MOCK_GATEWAY":

                    st.warning(
                        "MOCK / DEMO Gateway"
                    )

                else:

                    st.info(
                        str(rail)
                    )


        # -----------------------------------------------------
        # NEGOTIATION POLICY
        # -----------------------------------------------------

        policy = passport.get(
            "negotiation_policy",
            {}
        )

        if policy:

            with st.expander(
                "🤝 Negotiation Policy",
                expanded=False
            ):

                st.write(
                    f"**Negotiation Enabled:** "
                    f"`{policy.get('enabled', 'N/A')}`"
                )

                st.write(
                    f"**Minimum Margin:** "
                    f"`{policy.get('min_margin_pct', 'N/A')}%`"
                )

                st.write(
                    f"**Maximum Discount:** "
                    f"`{policy.get('max_discount_pct', 'N/A')}%`"
                )

                st.write(
                    f"**Bulk Threshold:** "
                    f"`{policy.get('bulk_threshold_qty', 'N/A')} units`"
                )

                st.write(
                    f"**Quote TTL:** "
                    f"`{policy.get('quote_ttl_seconds', 'N/A')} seconds`"
                )


        # -----------------------------------------------------
        # INVENTORY
        # -----------------------------------------------------

        st.markdown(
            "#### 📦 Live Inventory"
        )

        catalog = passport.get(
            "catalog",
            []
        )

        if catalog:

            for item in catalog:

                product_name = item.get(
                    "name",
                    "Unknown Product"
                )

                with st.expander(
                    f"⌨️ {product_name}",
                    expanded=True
                ):

                    st.write(
                        f"**Product ID:** "
                        f"`{item.get('product_id', 'N/A')}`"
                    )

                    st.write(
                        f"**Category:** "
                        f"`{item.get('category', 'N/A')}`"
                    )

                    st.write(
                        f"**Retail:** "
                        f"{paise_to_inr(item.get('retail_price_paise', 0))}"
                    )

                    st.write(
                        f"**Cost:** "
                        f"{paise_to_inr(item.get('cost_price_paise', 0))}"
                    )


                    stock_col_1, stock_col_2 = st.columns(2)

                    stock_col_1.metric(
                        "Available",
                        item.get(
                            "stock_available",
                            0
                        )
                    )

                    stock_col_2.metric(
                        "Reserved",
                        item.get(
                            "stock_reserved",
                            0
                        )
                    )

                    stock_col_3, stock_col_4 = st.columns(2)

                    stock_col_3.metric(
                        "Sold",
                        item.get(
                            "stock_sold",
                            0
                        )
                    )

                    stock_col_4.metric(
                        "Total",
                        item.get(
                            "stock_total",
                            0
                        )
                    )

        else:

            st.info(
                "No catalog items returned."
            )

    else:

        st.info(
            "Fetch the Merchant Passport "
            "to inspect live merchant information."
        )


# =============================================================
# COLUMN 2
# BUYER AGENT + TRANSACTION
# =============================================================

with col_transaction:

    st.subheader(
        "🤖 Autonomous Transaction"
    )

    st.caption(
        "Buyer mandate → Merchant negotiation → "
        "Stock reservation → Policy validation → "
        "Test order creation"
    )


    # ---------------------------------------------------------
    # NATURAL LANGUAGE BUYER INTENT
    # ---------------------------------------------------------

    st.markdown("#### 🧠 Natural Language Intent")
    st.caption(
        "The Buyer Agent converts a natural-language purchase goal "
        "into a typed, bounded mandate. The deterministic policy "
        "engine still controls transaction approval."
    )

    user_prompt = st.text_area(
        "Purchase Goal",
        value=(
            "I need 10 mechanical wireless keyboards for my team "
            "under ₹25,000 from TechGear Store."
        ),
        height=90,
        key="natural_language_prompt"
    )

    parse_col_1, parse_col_2 = st.columns([1, 1])

    if parse_col_1.button(
        "🧠 Parse Intent",
        use_container_width=True,
        key="parse_intent_button"
    ):
        with st.spinner(
            "Buyer Agent is converting the request into a bounded mandate..."
        ):
            try:
                response = requests.post(
                    f"{API_BASE}/api/v1/agent/parse-intent",
                    json={"prompt": user_prompt},
                    timeout=30
                )
                response_data = get_json_response(response)

                if response.status_code == 200:
                    st.session_state["parsed_mandate"] = response_data
                    st.session_state["intent_parse_message"] = (
                        "Natural-language request converted into a typed mandate."
                    )

                    parsed_mandate_id = response_data.get("mandate_id")
                    if parsed_mandate_id:
                        st.session_state["mandate_id_value"] = parsed_mandate_id
                        st.session_state["audit_mandate_value"] = parsed_mandate_id
                        st.session_state["audit_mandate_input"] = parsed_mandate_id

                    st.success("Intent parsed successfully.")
                else:
                    detail = response_data.get("detail", response_data)
                    st.error(f"Intent parsing failed: {detail}")

            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to the FastAPI backend.")
            except Exception as e:
                st.error(f"Intent parser error: {e}")

    if parse_col_2.button(
        "↩️ Use Manual Values",
        use_container_width=True,
        key="clear_parsed_intent_button"
    ):
        st.session_state["parsed_mandate"] = None
        st.session_state["intent_parse_message"] = None
        st.rerun()

    parsed_mandate = st.session_state.get("parsed_mandate")

    # ---------------------------------------------------------
    # MANDATE SOURCE
    # ---------------------------------------------------------

    if parsed_mandate:
        parsed_budget_paise = int(
            parsed_mandate.get("max_budget_paise", 2500000)
        )
        parsed_quantity = int(
            parsed_mandate.get("target_quantity", 10)
        )
        parsed_category = parsed_mandate.get(
            "category", "PERIPHERALS_KEYBOARDS"
        )
        parsed_merchants = parsed_mandate.get(
            "allowed_merchants", ["mer_techgear_01"]
        )
        parsed_mandate_id = parsed_mandate.get(
            "mandate_id", st.session_state["mandate_id_value"]
        )

        st.markdown("#### 📜 Parsed Bounded Mandate")
        parsed_col_1, parsed_col_2, parsed_col_3 = st.columns(3)
        parsed_col_1.metric(
            "Budget Cap", paise_to_inr(parsed_budget_paise)
        )
        parsed_col_2.metric("Quantity Cap", parsed_quantity)
        parsed_col_3.metric("Category", parsed_category)
        st.caption(
            "Allowed Merchant(s): " + ", ".join(
                str(merchant) for merchant in parsed_merchants
            )
        )

        with st.expander("View Parsed Mandate JSON"):
            st.json(parsed_mandate)

        st.info(
            "These mandate bounds came from the Buyer Agent. "
            "You may still demonstrate attacks below; the Payment "
            "Trust Engine must enforce the final boundaries."
        )

        default_budget_inr = parsed_budget_paise / 100
        default_quantity = parsed_quantity
        default_bid_inr = parsed_budget_paise / max(parsed_quantity, 1)
        active_category = parsed_category
        active_merchants = parsed_merchants
        active_mandate_id = parsed_mandate_id

    else:
        st.markdown("#### ✍️ Manual Bounded Mandate")
        st.caption(
            "No parsed mandate is active. Manual values are shown "
            "for reproducible security and red-team demonstrations."
        )
        default_budget_inr = 25000.0
        default_quantity = 10
        default_bid_inr = 2400.0
        active_category = "PERIPHERALS_KEYBOARDS"
        active_merchants = ["mer_techgear_01"]
        active_mandate_id = st.session_state["mandate_id_value"]

    # ---------------------------------------------------------
    # BUYER CONTROLS
    # ---------------------------------------------------------

    budget_inr = st.number_input(
        "Maximum Authorized Budget (₹)",
        min_value=1.0,
        value=float(default_budget_inr),
        step=500.0,
        key=("budget_input_parsed" if parsed_mandate else "budget_input")
    )

    target_quantity = st.number_input(
        "Authorized Quantity",
        min_value=1,
        value=int(default_quantity),
        step=1,
        key=("quantity_input_parsed" if parsed_mandate else "quantity_input")
    )

    bid_inr = st.number_input(
        "Initial Unit Bid (₹)",
        min_value=1.0,
        value=float(default_bid_inr),
        step=50.0,
        key=("bid_input_parsed" if parsed_mandate else "bid_input")
    )

    mandate_id = st.text_input(
        "Mandate ID",
        value=active_mandate_id,
        key=("mandate_input_parsed" if parsed_mandate else "mandate_input")
    )

    st.session_state["mandate_id_value"] = mandate_id

    # ---------------------------------------------------------
    # RED TEAM DEMO
    # ---------------------------------------------------------

    st.markdown("#### 🧪 Red-Team Security Demo")
    attack_col_1, attack_col_2, attack_col_3 = st.columns(3)

    attack_col_1.button(
        "💥 Budget",
        on_click=arm_budget_attack,
        use_container_width=True,
        key="budget_attack_button"
    )
    attack_col_2.button(
        "⚠️ Quantity",
        on_click=arm_quantity_attack,
        use_container_width=True,
        key="quantity_attack_button"
    )
    attack_col_3.button(
        "🔁 Replay",
        on_click=arm_replay_attack,
        use_container_width=True,
        key="replay_attack_button"
    )

    attack_mode = st.session_state.get("attack_mode")

    # ---------------------------------------------------------
    # EFFECTIVE TRANSACTION VALUES
    # ---------------------------------------------------------

    effective_budget_inr = budget_inr
    effective_quantity = int(target_quantity)
    effective_bid_inr = bid_inr

    if attack_mode == "budget":
        effective_bid_inr = 3500.0
        st.error(
            "💥 Budget attack armed: the request will attempt ₹3,500 per unit."
        )

    elif attack_mode == "quantity":
        effective_quantity = 15
        st.error(
            "⚠️ Quantity tampering armed: the request will attempt 15 units."
        )

    elif attack_mode == "replay":
        previous_bid_paise = st.session_state.get(
            "last_successful_bid_paise",
            int(round(bid_inr * 100))
        )
        effective_bid_inr = previous_bid_paise / 100
        effective_quantity = st.session_state.get(
            "last_successful_quantity",
            int(target_quantity)
        )
        st.warning(
            "🔁 Replay test armed using the previous successful mandate."
        )

    # ---------------------------------------------------------
    # CALCULATE VALUES
    # ---------------------------------------------------------

    budget_paise = int(round(effective_budget_inr * 100))
    bid_paise = int(round(effective_bid_inr * 100))

    # ---------------------------------------------------------
    # TRANSACTION PREVIEW
    # ---------------------------------------------------------

    preview_col_1, preview_col_2, preview_col_3 = st.columns(3)
    preview_col_1.metric("Budget", paise_to_inr(budget_paise))
    preview_col_2.metric("Quantity", effective_quantity)
    preview_col_3.metric("Bid / Unit", paise_to_inr(bid_paise))

    with st.expander("📜 View Active Mandate Preview"):
        mandate_preview = {
            "mandate_id": mandate_id,
            "user_id": "usr_buyer_99",
            "category": active_category,
            "allowed_merchants": active_merchants,
            "max_budget_paise": budget_paise,
            "target_quantity": effective_quantity,
            "created_at": int(time.time()),
            "expiry_seconds": 1800
        }
        st.json(mandate_preview)


    # ---------------------------------------------------------
    # EXECUTE TRANSACTION
    # ---------------------------------------------------------

    execute_clicked = st.button(
        "🚀 Execute Transaction",
        type="primary",
        use_container_width=True,
        key="execute_transaction_button"
    )


    if execute_clicked:

        created_at = int(
            time.time()
        )


        payload = {
            "mandate_id": mandate_id,
            "user_id": "usr_buyer_99",
            "category": active_category,
            "allowed_merchants": active_merchants,
            "max_budget_paise": budget_paise,
            "target_quantity": effective_quantity,
            "created_at": created_at,
            "expiry_seconds": 1800
        }


        with st.spinner(
            "🤖 Negotiating with merchant..."
        ):

            try:

                response = requests.post(
                    f"{API_BASE}/api/v1/agent/transact",
                    params={
                        "product_id": "prod_kb_01",
                        "bid_unit_price_paise": bid_paise
                    },
                    json=payload,
                    timeout=30
                )


                response_data = (
                    get_json_response(
                        response
                    )
                )


                st.session_state[
                    "latest_response"
                ] = {
                    "status_code": response.status_code,
                    "data": response_data,
                    "mandate_id": mandate_id,
                    "request_payload": payload
                }


                st.session_state[
                    "audit_mandate_value"
                ] = mandate_id

                # Safe:
                # audit widget key will already have
                # the same value during normal execution.
                # We do NOT modify mandate_input here.

                st.session_state[
                    "audit_trail"
                ] = None


                # -------------------------------------------------
                # SUCCESS / REPLAY
                # -------------------------------------------------

                if response.status_code == 200:

                    transaction_status = (
                        response_data.get(
                            "status",
                            ""
                        )
                    )


                    successful_statuses = [

                        "ORDER_CREATED_TEST_MODE",

                        "ORDER_CREATED_MOCK_MODE",

                        "ORDER_CREATED_SAFELY",

                        "REPLAY_SUPPRESSED_EXISTING_ORDER"

                    ]


                    if transaction_status in successful_statuses:

                        st.session_state[
                            "last_successful_mandate"
                        ] = mandate_id


                        if (
                            transaction_status
                            !=
                            "REPLAY_SUPPRESSED_EXISTING_ORDER"
                        ):

                            st.session_state[
                                "last_successful_bid_paise"
                            ] = bid_paise

                            st.session_state[
                                "last_successful_quantity"
                            ] = effective_quantity


                # -------------------------------------------------
                # FETCH AUDIT AUTOMATICALLY
                # -------------------------------------------------

                fetch_audit_trail(
                    mandate_id
                )


                # -------------------------------------------------
                # CLEAR ONE-TIME ATTACK MODES
                # -------------------------------------------------

                if attack_mode in [
                    "budget",
                    "quantity"
                ]:

                    st.session_state[
                        "attack_mode"
                    ] = None


            except requests.exceptions.ConnectionError:

                st.error(
                    "❌ Cannot connect to FastAPI backend."
                )

                st.code(
                    "uvicorn app:app --reload"
                )


            except Exception as e:

                st.error(
                    f"API Error: {e}"
                )


    # =========================================================
    # DISPLAY LATEST RESULT
    # =========================================================

    latest_response = st.session_state.get(
        "latest_response"
    )


    if latest_response:

        st.divider()

        st.markdown(
            "### 📊 Transaction Result"
        )


        status_code = latest_response.get(
            "status_code"
        )

        data = latest_response.get(
            "data",
            {}
        )


        # -----------------------------------------------------
        # SUCCESS RESPONSE
        # -----------------------------------------------------

        if status_code == 200:

            transaction_status = data.get(
                "status",
                ""
            )


            # -------------------------------------------------
            # REPLAY SUPPRESSED
            # -------------------------------------------------

            if (
                transaction_status
                ==
                "REPLAY_SUPPRESSED_EXISTING_ORDER"
            ):

                st.warning(
                    "🔁 Replay Attack Suppressed"
                )


                st.success(
                    "Duplicate transaction prevented. "
                    "The existing order was returned."
                )


                result_col_1, result_col_2 = (
                    st.columns(2)
                )


                result_col_1.metric(
                    "Existing Order",
                    data.get(
                        "razorpay_order_id",
                        "N/A"
                    )
                )


                result_col_2.metric(
                    "Amount",
                    paise_to_inr(
                        data.get(
                            "amount_paise",
                            0
                        )
                    )
                )


                st.caption(
                    f"Reason: "
                    f"{data.get('reason_code', 'IDEMPOTENT_CACHED_RESULT')}"
                )


            # -------------------------------------------------
            # ORDER CREATED
            # -------------------------------------------------

            elif transaction_status in [

                "ORDER_CREATED_TEST_MODE",

                "ORDER_CREATED_MOCK_MODE",

                "ORDER_CREATED_SAFELY"

            ]:

                order_id = data.get(
                    "razorpay_order_id",
                    ""
                )


                if (
                    order_id
                    and
                    order_id.startswith(
                        "order_mock_"
                    )
                ):

                    st.warning(
                        "🟡 MOCK / DEMO ORDER CREATED"
                    )

                    st.caption(
                        "No real payment occurred. "
                        "This is an explicitly labelled "
                        "demo fallback."
                    )


                else:

                    st.success(
                        "🟢 ORDER CREATED IN TEST MODE"
                    )

                    st.caption(
                        "An order was created successfully. "
                        "Order creation does NOT mean "
                        "payment settlement."
                    )


                result_col_1, result_col_2 = (
                    st.columns(2)
                )


                result_col_1.metric(
                    "Amount",
                    paise_to_inr(
                        data.get(
                            "amount_paise",
                            0
                        )
                    )
                )


                result_col_2.metric(
                    "Savings",
                    paise_to_inr(
                        data.get(
                            "negotiated_savings_paise",
                            0
                        )
                    )
                )


                st.write(
                    f"**Order ID:** "
                    f"`{order_id}`"
                )
                if data.get("cross_sell_offer"):
                    st.markdown("---")

                    st.info(
                        f"📈 **Revenue Growth AI (Merchant Agent)**\n\n"
                        f"{data['cross_sell_offer']['pitch']}"
                )


                st.write(
                    f"**Decision:** "
                    f"`{data.get('decision', 'ALLOW')}`"
                )


                st.write(
                    f"**Reason Code:** "
                    f"`{data.get('reason_code', 'N/A')}`"
                )


                audit_trail = data.get(
                    "audit_trail",
                    {}
                )


                quote_id = audit_trail.get(
                    "quote_id"
                )


                idempotency_key = (
                    audit_trail.get(
                        "idempotency_key"
                    )
                )


                if quote_id:

                    st.write(
                        f"**Quote ID:** "
                        f"`{quote_id}`"
                    )


                if idempotency_key:

                    with st.expander(
                        "🔐 Idempotency Key"
                    ):

                        st.code(
                            idempotency_key
                        )


            # -------------------------------------------------
            # UNKNOWN SUCCESS
            # -------------------------------------------------

            else:

                st.info(
                    "Transaction completed."
                )

                st.json(
                    data
                )


        # -----------------------------------------------------
        # BLOCKED RESPONSE
        # -----------------------------------------------------

        else:

            st.error(
                "🚨 BLOCKED BY PAYMENT TRUST ENGINE"
            )


            detail = data.get(
                "detail",
                data
            )


            if isinstance(
                detail,
                dict
            ):

                decision = detail.get(
                    "decision",
                    "BLOCK"
                )

                reason_code = detail.get(
                    "reason_code",
                    "UNKNOWN"
                )

                message = detail.get(
                    "message",
                    detail.get(
                        "error",
                        str(detail)
                    )
                )

            else:

                decision = "BLOCK"

                reason_code = "UNKNOWN"

                message = str(
                    detail
                )


            result_col_1, result_col_2 = (
                st.columns(2)
            )


            result_col_1.metric(
                "Decision",
                decision
            )


            result_col_2.metric(
                "Reason Code",
                reason_code
            )


            st.write(
                f"**Reason:** {message}"
            )


            st.caption(
                "The AI cannot override this decision. "
                "Policy evaluation is deterministic."
            )


    # ---------------------------------------------------------
    # CLEAR ATTACK MODE
    # ---------------------------------------------------------

    if attack_mode:

        if st.button(
            "✖ Clear Demo Scenario",
            use_container_width=True,
            key="clear_attack_button"
        ):

            clear_attack_mode()

            st.rerun()


    # ---------------------------------------------------------
    # START NEW MANDATE
    #
    # IMPORTANT:
    # Using on_click callback prevents Streamlit session
    # state modification error.
    # ---------------------------------------------------------

    st.divider()


    st.button(
        "🆕 Start New Mandate",
        on_click=start_new_mandate,
        use_container_width=True,
        key="new_mandate_button"
    )


# =============================================================
# COLUMN 3
# AUDIT LEDGER
# =============================================================

with col_audit:

    st.subheader(
        "🔐 Audit Timeline"
    )

    st.caption(
        "Persistent chronological event telemetry."
    )


    # ---------------------------------------------------------
    # AUDIT INPUT
    # ---------------------------------------------------------

    target_mandate = st.text_input(
        "Mandate ID to Inspect",
        key="audit_mandate_input"
    )


    st.session_state[
        "audit_mandate_value"
    ] = target_mandate


    # ---------------------------------------------------------
    # LOAD AUDIT
    # ---------------------------------------------------------

    if st.button(
        "🔍 Load Audit Trail",
        use_container_width=True,
        key="load_audit_button"
    ):

        st.session_state[
            "audit_trail"
        ] = None


        with st.spinner(
            "Loading audit telemetry..."
        ):

            success, audit_data = (
                fetch_audit_trail(
                    target_mandate
                )
            )


        if success:

            st.success(
                "Audit trail loaded."
            )

        else:

            detail = audit_data.get(
                "detail",
                audit_data
            )


            if isinstance(
                detail,
                dict
            ):

                message = detail.get(
                    "message",
                    detail.get(
                        "error",
                        str(detail)
                    )
                )

            else:

                message = str(
                    detail
                )


            st.warning(
                message
            )


    # ---------------------------------------------------------
    # DISPLAY AUDIT
    # ---------------------------------------------------------

    audit_data = st.session_state.get(
        "audit_trail"
    )


    if audit_data:

        audit_mandate = audit_data.get(
            "mandate_id"
        )


        # Only display if current mandate matches
        if (
            audit_mandate == target_mandate
            or audit_mandate is None
        ):

            transaction_status = (
                audit_data.get(
                    "transaction_status",
                    "NOT_FOUND"
                )
            )


            total_events = audit_data.get(
                "total_events",
                0
            )


            metric_1, metric_2 = st.columns(2)


            metric_1.metric(
                "Events",
                total_events
            )


            metric_2.metric(
                "Transaction",
                transaction_status
            )


            timeline = audit_data.get(
                "timeline",
                []
            )


            if timeline:

                st.markdown(
                    "#### Event Timeline"
                )


                df = pd.DataFrame(
                    timeline
                )


                # -------------------------------------------------
                # FORMAT TIMESTAMP
                # -------------------------------------------------

                if (
                    "timestamp"
                    in df.columns
                ):

                    df[
                        "time"
                    ] = pd.to_datetime(
                        df["timestamp"],
                        unit="s",
                        errors="coerce"
                    ).dt.strftime(
                        "%H:%M:%S"
                    )


                # -------------------------------------------------
                # SELECT AVAILABLE COLUMNS
                # -------------------------------------------------

                display_columns = []


                for column in [

                    "time",

                    "actor",

                    "event_type",

                    "status",

                    "reason_code"

                ]:

                    if column in df.columns:

                        display_columns.append(
                            column
                        )


                if display_columns:

                    st.dataframe(
                        df[
                            display_columns
                        ],
                        use_container_width=True,
                        hide_index=True
                    )


                with st.expander(
                    "📄 View Complete Audit Events"
                ):

                    st.json(
                        timeline
                    )


            else:

                st.info(
                    "No audit events found."
                )


        else:

            st.info(
                "Load an audit trail for the "
                "currently entered Mandate ID."
            )


    else:

        st.info(
            "Execute a transaction or load a "
            "Mandate ID to inspect the audit timeline."
        )


# =============================================================
# FOOTER
# =============================================================

st.divider()


footer_col_1, footer_col_2 = st.columns(
    [2, 1]
)


with footer_col_1:

    st.caption(
        "🛡️ AgentReady • A2A Negotiation • "
        "Scoped Mandates • Deterministic Policy Control • "
        "Stock Reservation • Idempotency Protection • "
        "Persistent Audit Telemetry"
    )


with footer_col_2:

    if backend_online:

        st.caption(
            "Backend: 🟢 Connected"
        )

    else:

        st.caption(
            "Backend: 🔴 Disconnected"
        )


st.caption(
    "Demo disclosure: Razorpay integration is intended "
    "for TEST MODE when configured. Creating an order "
    "does not represent completed payment settlement."
)