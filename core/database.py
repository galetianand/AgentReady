import os
import time

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Text,
)

from sqlalchemy.orm import declarative_base, sessionmaker


# =============================================================
# DATABASE CONFIGURATION
# =============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./agentready_ledger.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# =============================================================
# PRODUCT INVENTORY
# =============================================================

class ProductInventory(Base):
    """
    Stateful inventory.

    Invariant:
        stock_total =
        stock_available +
        stock_reserved +
        stock_sold

    All prices are stored as integer paise.
    """

    __tablename__ = "product_inventory"

    product_id = Column(
        String(64),
        primary_key=True,
        index=True
    )

    merchant_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    name = Column(
        String(128),
        nullable=False
    )

    category = Column(
        String(64),
        nullable=False,
        index=True
    )

    retail_price_paise = Column(
        Integer,
        nullable=False
    )

    cost_price_paise = Column(
        Integer,
        nullable=False
    )

    stock_total = Column(
        Integer,
        nullable=False
    )

    stock_available = Column(
        Integer,
        nullable=False
    )

    stock_reserved = Column(
        Integer,
        default=0,
        nullable=False
    )

    stock_sold = Column(
        Integer,
        default=0,
        nullable=False
    )

    updated_at = Column(
        Integer,
        default=lambda: int(time.time()),
        nullable=False
    )


# =============================================================
# STOCK RESERVATION + TIME-LOCKED QUOTE
# =============================================================

class StockReservationQuote(Base):
    """
    Persistent negotiated quote with temporary stock reservation.

    Possible statuses:
        RESERVED
        CONSUMED
        RELEASED
        EXPIRED
        CANCELLED
    """

    __tablename__ = "stock_reservation_quotes"

    quote_id = Column(
        String(64),
        primary_key=True,
        index=True
    )

    mandate_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    merchant_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    product_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    unit_price_paise = Column(
        Integer,
        nullable=False
    )

    shipping_cost_paise = Column(
        Integer,
        default=0,
        nullable=False
    )

    total_amount_paise = Column(
        Integer,
        nullable=False
    )

    status = Column(
        String(32),
        default="RESERVED",
        nullable=False,
        index=True
    )

    created_at = Column(
        Integer,
        default=lambda: int(time.time()),
        nullable=False
    )

    expires_at = Column(
        Integer,
        nullable=False,
        index=True
    )

    signature_hash = Column(
        String(64),
        nullable=True
    )


# =============================================================
# TRANSACTION LEDGER
# =============================================================

class TransactionLedger(Base):
    """
    Primary transaction execution ledger.

    All money values use integer paise.

    idempotency_key is UNIQUE to prevent duplicate
    order/payment creation.
    """

    __tablename__ = "transaction_ledger"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    mandate_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    merchant_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    product_id = Column(
        String(64),
        nullable=False
    )

    quote_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    idempotency_key = Column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    unit_price_paise = Column(
        Integer,
        nullable=False
    )

    shipping_cost_paise = Column(
        Integer,
        default=0,
        nullable=False
    )

    total_amount_paise = Column(
        Integer,
        nullable=False
    )

    currency = Column(
        String(8),
        default="INR",
        nullable=False
    )

    razorpay_order_id = Column(
        String(64),
        nullable=True
    )

    payment_mode = Column(
        String(32),
        nullable=False,
        default="MOCK_DEMO"
    )

    status = Column(
        String(32),
        nullable=False
    )

    created_at = Column(
        Integer,
        default=lambda: int(time.time()),
        nullable=False
    )


# =============================================================
# APPEND-ONLY AUDIT EVENT LOG
# =============================================================

class AuditEventLog(Base):
    """
    Append-only chronological audit telemetry.

    SQLite provides persistence for this demo.

    This must NOT be described as legally immutable
    or cryptographically tamper-proof storage.
    """

    __tablename__ = "audit_event_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    mandate_id = Column(
        String(64),
        nullable=False,
        index=True
    )

    quote_id = Column(
        String(64),
        nullable=True,
        index=True
    )

    order_id = Column(
        String(64),
        nullable=True,
        index=True
    )

    idempotency_key = Column(
        String(64),
        nullable=True,
        index=True
    )

    event_type = Column(
        String(64),
        nullable=False
    )

    actor = Column(
        String(64),
        nullable=False
    )

    decision = Column(
        String(32),
        nullable=True
    )

    status = Column(
        String(32),
        nullable=False
    )

    reason_code = Column(
        String(64),
        nullable=True
    )

    amount_paise = Column(
        Integer,
        nullable=True
    )

    payload = Column(
        Text,
        nullable=False
    )

    timestamp = Column(
        Integer,
        default=lambda: int(time.time()),
        nullable=False,
        index=True
    )


# =============================================================
# DATABASE INITIALIZATION
# =============================================================

Base.metadata.create_all(bind=engine)


# =============================================================
# DEMO DATABASE SEED
# =============================================================

def seed_database(db):
    """
    Seeds the demo catalog if products do not already exist.

    Existing products are never overwritten.
    This allows inventory state to remain persistent between runs.
    """

    # ---------------------------------------------------------
    # PRIMARY PRODUCT: MECHANICAL WIRELESS KEYBOARD
    # ---------------------------------------------------------

    existing_keyboard = (
        db.query(ProductInventory)
        .filter(
            ProductInventory.product_id == "prod_kb_01"
        )
        .first()
    )

    if not existing_keyboard:

        keyboard = ProductInventory(
            product_id="prod_kb_01",
            merchant_id="mer_techgear_01",
            name="Mechanical Wireless Keyboard",
            category="PERIPHERALS_KEYBOARDS",

            # ₹2,800.00
            retail_price_paise=280000,

            # ₹1,900.00
            cost_price_paise=190000,

            stock_total=50,
            stock_available=50,
            stock_reserved=0,
            stock_sold=0
        )

        db.add(keyboard)


    # ---------------------------------------------------------
    # COMPLEMENTARY PRODUCT: PRO GLIDE DESK MAT
    # CROSS-SELL / UPSELL PRODUCT
    # ---------------------------------------------------------

    existing_mousepad = (
        db.query(ProductInventory)
        .filter(
            ProductInventory.product_id == "prod_mp_01"
        )
        .first()
    )

    if not existing_mousepad:

        mousepad = ProductInventory(
            product_id="prod_mp_01",
            merchant_id="mer_techgear_01",
            name="Pro Glide Desk Mat",
            category="PERIPHERALS_ACCESSORIES",

            # ₹999.00
            retail_price_paise=99900,

            # ₹400.00
            cost_price_paise=40000,

            stock_total=100,
            stock_available=100,
            stock_reserved=0,
            stock_sold=0
        )

        db.add(mousepad)


    # ---------------------------------------------------------
    # COMMIT ALL NEW SEED PRODUCTS
    # ---------------------------------------------------------

    db.commit()

# =============================================================
# DATABASE DEPENDENCY
# =============================================================

def get_db():

    db = SessionLocal()

    try:

        seed_database(db)

        yield db

    finally:

        db.close()