"""Seed fifteen diverse, hand-authored invoices with unique audit trails for the CHASR demo."""

from datetime import datetime, timedelta

from backend.database import SessionLocal, init_db
from backend.clock import now
from backend.engines import ledger as ledger_engine
from backend.models import Customer, EscalationStage, Invoice, InvoiceStatus, Ledger, LedgerEventType, Promise, PromiseConfidence, PromiseStatus

MANUAL_DEMO_RECORDS = [
    # --- THE 3 "GOLDEN" DEMO SCENARIOS ---
    
    # 1. Northstar: Standard Nudge escalation
    {
        "customer_id": 10001,
        "customer_name": "Northstar Components",
        "gstin": "29AAAAA1001A1Z5",
        "phone": "+919900000001",
        "email": "finance@northstar.example",
        "amount": 185000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.nudge,
        "days_overdue": 18, 
        "needs_review": False,
        "initial_message": "Invoice received. We are reviewing accounts and will process payment by next Tuesday.",
    },
    # 2. BluePeak: The AI Math Flex (1 Lakh total)
    {
        "customer_id": 10002,
        "customer_name": "BluePeak Logistics",
        "gstin": "27BBBBB1002B2Z6",
        "phone": "+919900000002",
        "email": "accounts@bluepeak.example",
        "amount": 100000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.nudge,
        "days_overdue": 5,
        "needs_review": False,
        "initial_message": "We are waiting on client disbursement and will clear 50% by Thursday and the rest by month-end.",
    },
    # 3. Mitra: Human Handoff / Evasive Case
    {
        "customer_id": 10003,
        "customer_name": "Mitra Retail Group",
        "gstin": "19CCCCC1003C3Z7",
        "phone": "+919900000003",
        "email": "ap@mitra.example",
        "amount": 240000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 45,
        "needs_review": True, 
        "initial_message": "We are facing severe cash flow issues right now. I will try to send something over whenever our clients finally pay us.",
    },

    # --- DIVERSE BACKGROUND PROFILES ---
    
    {
        "customer_id": 10004,
        "customer_name": "Cedar Works",
        "gstin": "06DDDDD1004D4Z8",
        "phone": "+919900000004",
        "email": "billing@cedar.example",
        "amount": 67000.0,
        "amount_paid": 67000.0,
        "status": InvoiceStatus.paid,
        "current_stage": EscalationStage.none,
        "days_overdue": 0,
        "needs_review": False,
        "initial_message": "Payment of 67000 completed via Razorpay gateway.",
    },
    {
        "customer_id": 10005,
        "customer_name": "Aster Systems",
        "gstin": "09EEEEE1005E5Z9",
        "phone": "+919900000005",
        "email": "finance@aster.example",
        "amount": 154000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 35,
        "needs_review": False,
        "initial_message": "We have scheduled a wire transfer of ₹1,54,000 for Friday morning without fail.",
    },
    {
        "customer_id": 10006,
        "customer_name": "Vanguard Tech",
        "gstin": "33FFFFF1006F6Z1",
        "phone": "+919900000006",
        "email": "ap@vanguard.example",
        "amount": 320000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 62,
        "needs_review": True,
        "initial_message": "Disputed the line items on this invoice. Escalating to management before releasing funds.",
    },
    {
        "customer_id": 10007,
        "customer_name": "Zenith Corp",
        "gstin": "21GGGGG1007G7Z2",
        "phone": "+919900000007",
        "email": "payments@zenith.example",
        "amount": 45000.0,
        "amount_paid": 45000.0,
        "status": InvoiceStatus.paid,
        "current_stage": EscalationStage.none,
        "days_overdue": 0,
        "needs_review": False,
        "initial_message": "Settled in full via net banking.",
    },
    {
        "customer_id": 10008,
        "customer_name": "Nexus Dynamics",
        "gstin": "07HHHHH1008H8Z3",
        "phone": "+919900000008",
        "email": "finance@nexus.example",
        "amount": 85000.0,
        "amount_paid": 40000.0,
        "status": InvoiceStatus.partially_paid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 28,
        "needs_review": False,
        "initial_message": "Cleared 40k as an advance installment. Balance of 45k will be cleared by the 15th.",
    },
    {
        "customer_id": 10009,
        "customer_name": "Horizon Media",
        "gstin": "24IIIII1009I9Z4",
        "phone": "+919900000009",
        "email": "accounts@horizon.example",
        "amount": 500000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 70,
        "needs_review": False,
        "initial_message": "Our accounts payable team is processing this. Expect a transfer early next week.",
    },
    {
        "customer_id": 10010,
        "customer_name": "Pioneer Supply",
        "gstin": "10JJJJJ1010J0Z5",
        "phone": "+919900000010",
        "email": "billing@pioneer.example",
        "amount": 25000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.written_off,
        "current_stage": EscalationStage.formal,
        "days_overdue": 120,
        "needs_review": False,
        "initial_message": "Company undergoing liquidation. Marked as bad debt.",
    },
    {
        "customer_id": 10011,
        "customer_name": "Quantum Goods",
        "gstin": "08KKKKK1011K1Z6",
        "phone": "+919900000011",
        "email": "ap@quantum.example",
        "amount": 125000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.nudge,
        "days_overdue": 10,
        "needs_review": False,
        "initial_message": "Thanks for the reminder. Will initiate payment tomorrow.",
    },
    {
        "customer_id": 10012,
        "customer_name": "Stellar Forge",
        "gstin": "11LLLLL1012L2Z7",
        "phone": "+919900000012",
        "email": "finance@stellar.example",
        "amount": 78000.0,
        "amount_paid": 78000.0,
        "status": InvoiceStatus.paid,
        "current_stage": EscalationStage.none,
        "days_overdue": 0,
        "needs_review": False,
        "initial_message": "Transaction closed successfully.",
    },
    {
        "customer_id": 10013,
        "customer_name": "Omni Builders",
        "gstin": "32MMMMM1013M3Z8",
        "phone": "+919900000013",
        "email": "payments@omni.example",
        "amount": 150000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 22,
        "needs_review": False,
        "initial_message": "Will clear ₹75,000 this Friday and the remaining balance next week.",
    },
    {
        "customer_id": 10014,
        "customer_name": "Aegis Security",
        "gstin": "04NNNNN1014N4Z9",
        "phone": "+919900000014",
        "email": "accounts@aegis.example",
        "amount": 850000.0,
        "amount_paid": 200000.0,
        "status": InvoiceStatus.partially_paid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 40,
        "needs_review": False,
        "initial_message": "Tranche 1 of 200k paid. Rest will follow milestone completions.",
    },
    {
        "customer_id": 10015,
        "customer_name": "Vertex Solutions",
        "gstin": "12OOOOO1015O5Z0",
        "phone": "+919900000015",
        "email": "billing@vertex.example",
        "amount": 110000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 55,
        "needs_review": False,
        "initial_message": "Invoice is stuck with tax auditors. Trying to expedite approval.",
    },
]

def seed_manual_demo():
    init_db()
    # Read virtual time before opening the seed transaction. Calling clock.now()
    # inside it opens a second SQLite writer and can lock Demo Reset.
    reference_time = now()
    session = SessionLocal()

    try:
        manual_customer_ids = [record["customer_id"] for record in MANUAL_DEMO_RECORDS]
        old_invoices = session.query(Invoice).filter(
            Invoice.customer_id.in_(manual_customer_ids)
        ).all()
        old_invoice_ids = [invoice.id for invoice in old_invoices]
        if old_invoice_ids:
            session.query(Promise).filter(Promise.invoice_id.in_(old_invoice_ids)).delete(
                synchronize_session=False
            )
            session.query(Ledger).filter(Ledger.invoice_id.in_(old_invoice_ids)).delete(
                synchronize_session=False
            )
            session.query(Invoice).filter(Invoice.id.in_(old_invoice_ids)).delete(
                synchronize_session=False
            )
            session.flush()

        for record in MANUAL_DEMO_RECORDS:
            customer = session.query(Customer).filter(Customer.id == record["customer_id"]).first()
            if customer is None:
                customer = Customer(
                    id=record["customer_id"],
                    name=record["customer_name"],
                    gstin=record["gstin"],
                    phone=record["phone"],
                    email=record["email"],
                )
                session.add(customer)
                session.flush()
            else:
                customer.name = record["customer_name"]
                customer.gstin = record["gstin"]
                customer.phone = record["phone"]
                customer.email = record["email"]

            due_date = reference_time - timedelta(days=record["days_overdue"])
            issued_date = due_date - timedelta(days=30)

            invoice = Invoice(customer_id=record["customer_id"])
            session.add(invoice)

            invoice.amount = record["amount"]
            invoice.amount_paid = record["amount_paid"]
            invoice.status = record["status"]
            invoice.current_stage = record["current_stage"]
            invoice.due_date = due_date
            invoice.issued_date = issued_date
            invoice.needs_review = record["needs_review"]
            session.flush()

            # Clear old ledger entries for this invoice to prevent duplication on re-seed
            session.query(Ledger).filter(Ledger.invoice_id == invoice.id).delete()
            session.flush()

            # Log invoice creation
            ledger_engine.append_entry(
                session,
                invoice.id,
                LedgerEventType.invoice_created,
                {
                    "source": "manual_demo_seed",
                    "customer_id": record["customer_id"],
                    "amount": record["amount"],
                },
            )

            # Log a unique historical reply/message so every customer has real variety
            ledger_engine.append_entry(
                session,
                invoice.id,
                LedgerEventType.reply_received,
                {
                    "text": record["initial_message"],
                },
            )

        # Give the two primary recording scenarios genuine, persisted history:
        # Northstar keeps promises; BluePeak breaks them. These are separate
        # closed invoices, so the live demo invoice remains untouched while
        # score_customer() derives visibly different scores from real rows.
        _seed_reliability_history(session, 10001, kept=True, reference=reference_time)
        _seed_reliability_history(session, 10002, kept=False, reference=reference_time)

        session.commit()
        print(f"Seeded {len(MANUAL_DEMO_RECORDS)} uniquely varied demo invoices successfully.")
    finally:
        session.close()


def _seed_reliability_history(session, customer_id: int, kept: bool, reference: datetime) -> None:
    for index in range(4):
        due_date = reference - timedelta(days=120 + index * 10)
        historical = Invoice(
            customer_id=customer_id,
            amount=100000.0,
            amount_paid=100000.0 if kept else 0.0,
            due_date=due_date,
            issued_date=due_date - timedelta(days=30),
            status=InvoiceStatus.paid if kept else InvoiceStatus.written_off,
            current_stage=EscalationStage.none if kept else EscalationStage.formal,
        )
        session.add(historical)
        session.flush()
        ledger_engine.append_entry(session, historical.id, LedgerEventType.invoice_created, {"source": "demo_reliability_history"})
        escalation_entry = ledger_engine.append_entry(session, historical.id, LedgerEventType.escalation_sent, {"stage": "nudge", "source": "demo_reliability_history"})
        ledger_engine.append_entry(session, historical.id, LedgerEventType.reply_received, {"text": "Synthetic historical commitment"})
        promise = Promise(
            invoice_id=historical.id,
            ledger_entry_id=escalation_entry.id,
            amount=historical.amount,
            promised_date=due_date + timedelta(days=3),
            confidence=PromiseConfidence.firm,
            status=PromiseStatus.kept_full if kept else PromiseStatus.broken,
            source_text="Seeded historical promise for the repeatable demo.",
        )
        session.add(promise)
        session.commit()
        ledger_engine.append_entry(session, historical.id, LedgerEventType.promise_status_updated, {"status": promise.status.value})

if __name__ == "__main__":
    seed_manual_demo()
