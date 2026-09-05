import json
import time

from sqlalchemy.orm import Session

from core.database import TransactionLedger, AuditEventLog


class AuditService:

    @staticmethod
    def log_event(
        db: Session,
        mandate_id: str,
        event_type: str,
        actor: str,
        status: str,
        payload: dict,
        quote_id: str = None
    ):
        """
        Appends a chronological audit event.

        This is demo telemetry stored in SQLite.
        It should not be described as legally immutable storage.
        """

        event = AuditEventLog(
            mandate_id=mandate_id,
            quote_id=quote_id,
            event_type=event_type,
            actor=actor,
            status=status,
            payload=json.dumps(payload),
            timestamp=int(time.time())
        )

        db.add(event)
        db.commit()

        return event

    @staticmethod
    def get_existing_transaction_by_idempotency(
        db: Session,
        idempotency_key: str
    ):
        """
        Returns an existing transaction if the same canonical
        idempotency key was already processed.
        """

        return (
            db.query(TransactionLedger)
            .filter(
                TransactionLedger.idempotency_key == idempotency_key
            )
            .first()
        )

    @staticmethod
    def create_transaction_record(
        db: Session,
        mandate_id: str,
        idempotency_key: str,
        merchant_id: str,
        product_id: str,
        quote_id: str,
        quantity: int,
        unit_price_paise: int,
        total_amount_paise: int,
        status: str,
        razorpay_order_id: str = None
    ) -> TransactionLedger:
        """
        Creates the persistent transaction record.

        All financial values are stored in integer paise.
        """

        record = TransactionLedger(
            mandate_id=mandate_id,
            idempotency_key=idempotency_key,
            merchant_id=merchant_id,
            product_id=product_id,
            quote_id=quote_id,
            quantity=quantity,
            unit_price_paise=unit_price_paise,
            total_amount_paise=total_amount_paise,
            razorpay_order_id=razorpay_order_id,
            status=status
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record