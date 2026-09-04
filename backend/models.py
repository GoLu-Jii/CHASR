# backend/models.py

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class InvoiceStatus(enum.Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"
    written_off = "written_off"
    escalation_exhausted = "escalation_exhausted"   # NEW — §9.4's terminal "handed to human" state

class EscalationStage(enum.Enum):
    none = "none"
    nudge = "nudge"
    firm = "firm"
    formal = "formal"

class LedgerEventType(enum.Enum):
    invoice_created = "invoice_created"
    escalation_sent = "escalation_sent"
    reply_received = "reply_received"
    promise_extracted = "promise_extracted"
    promise_status_updated = "promise_status_updated"
    payment_link_created = "payment_link_created"
    payment_received = "payment_received"
    escalated_to_human_review = "escalated_to_human_review"

class PromiseConfidence(enum.Enum):
    firm = "firm"
    soft = "soft"
    vague = "vague"

class PromiseStatus(enum.Enum):
    pending = "pending"
    kept_full = "kept_full"
    kept_partial = "kept_partial"
    broken = "broken"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    gstin = Column(String, nullable=True)
    phone = Column(String)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="customer")
    reliability_scores = relationship("CustomerReliability", back_populates="customer")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    amount = Column(Float, nullable=False)
    amount_paid = Column(Float, default=0.0)   # NEW — nothing tracked actual receipt before this; §9.3 needs it
    due_date = Column(DateTime, nullable=False)
    issued_date = Column(DateTime, default=datetime.utcnow)

    razorpay_invoice_id = Column(String, unique=True, index=True, nullable=True)

    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)
    current_stage = Column(Enum(EscalationStage), default=EscalationStage.none)
    last_contacted_at = Column(DateTime, nullable=True)
    contact_count = Column(Integer, default=0, nullable=False)

    customer = relationship("Customer", back_populates="invoices")
    ledger_entries = relationship("Ledger", back_populates="invoice")
    promises = relationship("Promise", back_populates="invoice")
    needs_review = Column(Boolean, default=False)
    razorpay_payment_link_id = Column(String, unique=True, index=True, nullable=True)


class Ledger(Base):
    """
    The audit trail. Append-only by construction — engines/ledger.py is the
    only code allowed to write here, via append_entry(). Never UPDATE/DELETE.
    """
    __tablename__ = "ledger"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    event_type = Column(Enum(LedgerEventType), nullable=False)

    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False, unique=True)

    invoice = relationship("Invoice", back_populates="ledger_entries")
    promises = relationship("Promise", back_populates="ledger_entry")


class Promise(Base):
    __tablename__ = "promises"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    ledger_entry_id = Column(Integer, ForeignKey("ledger.id"))

    amount = Column(Float, nullable=True)
    promised_date = Column(DateTime, nullable=True)
    confidence = Column(Enum(PromiseConfidence), nullable=False)
    status = Column(Enum(PromiseStatus), default=PromiseStatus.pending)

    source_text = Column(String, nullable=False)

    invoice = relationship("Invoice", back_populates="promises")
    ledger_entry = relationship("Ledger", back_populates="promises")


class CustomerReliability(Base):
    """
    Note: surrogate `id` PK + non-unique customer_id means this is an
    append-only HISTORY of scores, not one row per customer. Anywhere you
    need a customer's current score, order by computed_at DESC and take the
    latest row — reliability.py should own that query in one place.
    """
    __tablename__ = "customer_reliability"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    computed_at = Column(DateTime, default=datetime.utcnow)

    total_promises = Column(Integer, default=0)
    kept_full = Column(Integer, default=0)
    kept_partial = Column(Integer, default=0)
    broken = Column(Integer, default=0)

    kept_full_rate = Column(Float, default=0.0)
    broken_rate = Column(Float, default=0.0)
    avg_days_late = Column(Float, default=0.0)

    score = Column(Float, default=0.0)

    customer = relationship("Customer", back_populates="reliability_scores")
