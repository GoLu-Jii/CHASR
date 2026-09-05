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
        "customer_id": 10101,
        "customer_name": "Maple Ridge Foods",
        "gstin": "29AAAAA1001A1Z5",
        "phone": "+919900000001",
        "email": "finance@northstar.example",
        "amount": 92000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.nudge,
        # Kept equal to Harborline's starting age so one +7-day demo action
        # visibly proves that reliability, not invoice age alone, changes pace.
        "days_overdue": 13,
        "needs_review": False,
        "initial_message": "We have queued this for Friday's payment run.",
    },
    # 2. BluePeak: The AI Math Flex (1 Lakh total)
    {
        "customer_id": 10102,
        "customer_name": "Harborline Freight",
        "gstin": "27BBBBB1002B2Z6",
        "phone": "+919900000002",
        "email": "accounts@bluepeak.example",
        "amount": 210000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.nudge,
        "days_overdue": 13,
        "needs_review": False,
        "initial_message": "We can release 50% next Wednesday and the balance after our customer settles.",
    },
    # 3. Mitra: Human Handoff / Evasive Case
    {
        "customer_id": 10103,
        "customer_name": "Kite & Co. Retail",
        "gstin": "19CCCCC1003C3Z7",
        "phone": "+919900000003",
        "email": "ap@mitra.example",
        "amount": 138500.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 47,
        "needs_review": True, 
        "initial_message": "Cash flow is tight. We will try to pay something when our stores improve.",
    },

    # --- DIVERSE BACKGROUND PROFILES ---
    
    {
        "customer_id": 10104,
        "customer_name": "Orchid Health Labs",
        "gstin": "06DDDDD1004D4Z8",
        "phone": "+919900000004",
        "email": "billing@cedar.example",
        "amount": 76000.0,
        "amount_paid": 76000.0,
        "status": InvoiceStatus.paid,
        "current_stage": EscalationStage.none,
        "days_overdue": 0,
        "needs_review": False,
        "initial_message": "Settled in full through the payment gateway.",
    },
    {
        "customer_id": 10105,
        "customer_name": "Copperleaf Studio",
        "gstin": "09EEEEE1005E5Z9",
        "phone": "+919900000005",
        "email": "finance@aster.example",
        "amount": 184000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 31,
        "needs_review": False,
        "initial_message": "The transfer is approved and should leave our account Monday morning.",
    },
    {
        "customer_id": 10106,
        "customer_name": "Silver Oak Manufacturing",
        "gstin": "33FFFFF1006F6Z1",
        "phone": "+919900000006",
        "email": "ap@vanguard.example",
        "amount": 415000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 64,
        "needs_review": True,
        "initial_message": "We are disputing the delivery quantities and have paused payment pending review.",
    },
    {
        "customer_id": 10107,
        "customer_name": "Willowbrook Events",
        "gstin": "21GGGGG1007G7Z2",
        "phone": "+919900000007",
        "email": "payments@zenith.example",
        "amount": 48500.0,
        "amount_paid": 48500.0,
        "status": InvoiceStatus.paid,
        "current_stage": EscalationStage.none,
        "days_overdue": 0,
        "needs_review": False,
        "initial_message": "Paid after the event closeout was completed.",
    },
    {
        "customer_id": 10108,
        "customer_name": "Redwood Learning",
        "gstin": "07HHHHH1008H8Z3",
        "phone": "+919900000008",
        "email": "finance@nexus.example",
        "amount": 129000.0,
        "amount_paid": 39000.0,
        "status": InvoiceStatus.partially_paid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 26,
        "needs_review": False,
        "initial_message": "We paid the first 30%; the remaining amount follows after the grant drawdown.",
    },
    {
        "customer_id": 10109,
        "customer_name": "Blue Lantern Media",
        "gstin": "24IIIII1009I9Z4",
        "phone": "+919900000009",
        "email": "accounts@horizon.example",
        "amount": 560000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 76,
        "needs_review": False,
        "initial_message": "Our parent company is processing the approval; we expect an update next week.",
    },
    {
        "customer_id": 10110,
        "customer_name": "Meadowbrook Textiles",
        "gstin": "10JJJJJ1010J0Z5",
        "phone": "+919900000010",
        "email": "billing@pioneer.example",
        "amount": 31000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.written_off,
        "current_stage": EscalationStage.formal,
        "days_overdue": 118,
        "needs_review": False,
        "initial_message": "The account has entered insolvency proceedings and this balance is written off.",
    },
    {
        "customer_id": 10111,
        "customer_name": "Juniper Office Supply",
        "gstin": "08KKKKK1011K1Z6",
        "phone": "+919900000011",
        "email": "ap@quantum.example",
        "amount": 117500.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.nudge,
        "days_overdue": 11,
        "needs_review": False,
        "initial_message": "Please send the statement again; our new controller will review it tomorrow.",
    },
    {
        "customer_id": 10112,
        "customer_name": "Saffron Peak Exports",
        "gstin": "11LLLLL1012L2Z7",
        "phone": "+919900000012",
        "email": "finance@stellar.example",
        "amount": 86500.0,
        "amount_paid": 86500.0,
        "status": InvoiceStatus.paid,
        "current_stage": EscalationStage.none,
        "days_overdue": 0,
        "needs_review": False,
        "initial_message": "Export remittance cleared and the invoice is fully settled.",
    },
    {
        "customer_id": 10113,
        "customer_name": "Pinecrest Engineering",
        "gstin": "32MMMMM1013M3Z8",
        "phone": "+919900000013",
        "email": "payments@omni.example",
        "amount": 268000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 24,
        "needs_review": False,
        "initial_message": "We will send ₹100,000 this Friday and the rest after the installation sign-off.",
    },
    {
        "customer_id": 10114,
        "customer_name": "Amberline Security",
        "gstin": "04NNNNN1014N4Z9",
        "phone": "+919900000014",
        "email": "accounts@aegis.example",
        "amount": 735000.0,
        "amount_paid": 175000.0,
        "status": InvoiceStatus.partially_paid,
        "current_stage": EscalationStage.firm,
        "days_overdue": 39,
        "needs_review": False,
        "initial_message": "The initial deployment milestone was paid; two more milestones remain.",
    },
    {
        "customer_id": 10115,
        "customer_name": "Crescent Travel Services",
        "gstin": "12OOOOO1015O5Z0",
        "phone": "+919900000015",
        "email": "billing@vertex.example",
        "amount": 146000.0,
        "amount_paid": 0.0,
        "status": InvoiceStatus.unpaid,
        "current_stage": EscalationStage.formal,
        "days_overdue": 52,
        "needs_review": False,
        "initial_message": "The invoice is held while our auditors reconcile the travel credits.",
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
        _seed_reliability_history(session, 10101, kept=True, reference=reference_time)
        _seed_reliability_history(session, 10102, kept=False, reference=reference_time)

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
