import os
from contextlib import asynccontextmanager
from datetime import datetime

import joblib
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import config
from backend.clock import advance as advance_demo_clock, now as demo_now, reset as reset_demo_clock
from backend.database import get_db, init_db
from backend.engines import escalation, ledger, payments, promise_extraction, reliability
from backend.integrations import razorpay_client
from backend.ml.evaluate import run_batch_evaluation
from backend.models import Customer, CustomerReliability, Invoice, InvoiceStatus, Ledger, Promise

ml_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ml_model
    model_path = os.path.join(os.path.dirname(__file__), "ml", "reliability_model.joblib")
    if os.path.exists(model_path):
        ml_model = joblib.load(model_path)
        print("✅ ML Reliability Engine loaded into memory.")
    else:
        print("⚠️ Warning: ML model not found. Run train_reliability_model.py first.")

    init_db()
    ensure_demo_data()
    yield
    print("Shutting down CHASR API.")


app = FastAPI(title="CHASR Engine API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReplyPayload(BaseModel):
    text: str


class SimulateReplyPayload(ReplyPayload):
    invoice_id: int

class ActionResponse(BaseModel):
    status: str
    message: str


class CronRunResponse(ActionResponse):
    processed: int = 0
    updated_invoices: list[dict] = []
    run_at: str = ""


class AdvanceClockPayload(BaseModel):
    days: int


class PaymentPayload(BaseModel):
    amount_paid: float | None = None


def ensure_demo_data():
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        demo_count = db.query(Invoice).filter(Invoice.customer_id >= 10000).count()
        if demo_count > 0:
            return
    finally:
        db.close()
    # Keep synthetic history intact; seed only the deterministic demo slice.
    _seed_demo_data()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "CHASR"}


@app.get("/api/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    total_unpaid = db.query(func.sum(Invoice.amount)).filter(Invoice.status.in_([InvoiceStatus.unpaid, InvoiceStatus.partially_paid])).scalar() or 0
    active_unpaid_invoices = db.query(Invoice).filter(Invoice.status.in_([InvoiceStatus.unpaid, InvoiceStatus.partially_paid])).count()
    human_review_required = db.query(Invoice).filter(Invoice.needs_review.is_(True) | (Invoice.status == InvoiceStatus.escalation_exhausted)).count()
    return {
        "total_unpaid_inr": round(float(total_unpaid), 2),
        "active_unpaid_invoices": active_unpaid_invoices,
        "human_review_required": human_review_required,
    }


@app.get("/api/invoices")
def list_invoices(db: Session = Depends(get_db)):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id >= 10000)
        .order_by(Invoice.issued_date.desc())
        .limit(100)
        .all()
    )
    result = []
    for inv in invoices:
        days_overdue = max(0, (demo_now() - inv.due_date).days)
        latest_reply = (
            db.query(Ledger)
            .filter(
                Ledger.invoice_id == inv.id,
                Ledger.event_type == "reply_received",
            )
            .order_by(Ledger.id.desc())
            .first()
        )
        latest_escalation = (
            db.query(Ledger)
            .filter(
                Ledger.invoice_id == inv.id,
                Ledger.event_type == "escalation_sent",
            )
            .order_by(Ledger.id.desc())
            .first()
        )
        result.append({
            "id": inv.id,
            "customer_name": inv.customer.name if inv.customer else "Unknown",
            "amount": float(inv.amount),
            "amount_paid": float(inv.amount_paid or 0),
            "status": inv.status.value,
            "current_stage": (inv.current_stage.value if inv.current_stage else "none"),
            "due_date": inv.due_date.isoformat(),
            "days_overdue": days_overdue,
            "needs_review": bool(inv.needs_review),
            "reliability_score": reliability.score_customer(inv.customer_id, db),
            "last_customer_reply": (latest_reply.payload or {}).get("text") if latest_reply else None,
            "next_action": _next_action(db, inv),
            "next_message": (
                (latest_escalation.payload or {}).get("message_sent")
                if latest_escalation
                else _next_message(db, inv)
            ),
        })
    return result


@app.get("/api/invoices/{invoice_id}")
def get_invoice_detail(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {
        "id": invoice.id,
        "customer_name": invoice.customer.name if invoice.customer else "Unknown",
        "amount": float(invoice.amount),
        "amount_paid": float(invoice.amount_paid or 0),
        "status": invoice.status.value,
        "current_stage": invoice.current_stage.value if invoice.current_stage else "none",
        "due_date": invoice.due_date.isoformat(),
        "days_overdue": max(0, (demo_now() - invoice.due_date).days),
        "needs_review": bool(invoice.needs_review),
        "reliability_score": reliability.score_customer(invoice.customer_id, db),
        "next_action": _next_action(db, invoice),
        "next_message": _next_message(db, invoice),
        "razorpay_invoice_id": invoice.razorpay_invoice_id,
        "razorpay_payment_link_id": invoice.razorpay_payment_link_id,
        "promises": [
            {
                "id": promise.id,
                "amount": promise.amount,
                "promised_date": promise.promised_date.isoformat() if promise.promised_date else None,
                "confidence": promise.confidence.value,
                "status": promise.status.value,
                "source_text": promise.source_text,
            }
            for promise in invoice.promises
        ],
    }


def _next_action(db: Session, invoice: Invoice) -> str:
    return escalation.next_action(db, invoice)["action"]


def _next_message(db: Session, invoice: Invoice) -> str | None:
    return escalation.next_action(db, invoice)["message"]


@app.get("/api/invoices/{invoice_id}/ledger")
def get_invoice_audit_trail(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    entries = db.query(Ledger).filter(Ledger.invoice_id == invoice_id).order_by(Ledger.id.asc()).all()
    return {
        "invoice_id": invoice_id,
        "chain_integrity_valid": ledger.verify_chain(db, invoice_id),
        "ledger": [{
            "id": entry.id,
            "event": entry.event_type.value,
            "payload": entry.payload,
            "timestamp": entry.created_at.isoformat(),
            "prev_hash": entry.prev_hash,
            "hash": entry.hash,
        } for entry in entries],
    }


@app.post("/api/invoices/{invoice_id}/verify")
def verify_invoice_ledger(invoice_id: int, db: Session = Depends(get_db)):
    if not db.query(Invoice).filter(Invoice.id == invoice_id).first():
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"invoice_id": invoice_id, "chain_integrity_valid": ledger.verify_chain(db, invoice_id)}


@app.post("/api/invoices/{invoice_id}/razorpay")
def create_razorpay_test_objects(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    remaining = max(0.0, float(invoice.amount) - float(invoice.amount_paid or 0.0))
    next_promise = next(
        (
            promise for promise in sorted(
                invoice.promises,
                key=lambda item: item.promised_date or datetime.max,
            )
            if promise.status.value == "pending" and promise.amount
        ),
        None,
    )
    promised_amount = float(next_promise.amount) if next_promise else 0.0
    requested_amount = min(remaining, promised_amount) if promised_amount else remaining
    link = escalation._ensure_payment_link(db, invoice, amount=requested_amount)
    if link.get("error"):
        raise HTTPException(status_code=502, detail=f"Razorpay payment-link creation failed: {link['error']}")
    return {
        "status": "success",
        "invoice_id": invoice.id,
        "razorpay_invoice_id": invoice.razorpay_invoice_id,
        "razorpay_payment_link_id": invoice.razorpay_payment_link_id,
        "payment_link": link.get("short_url"),
        "amount": requested_amount,
        "mocked": bool(link.get("mocked", "mock" in str(link.get("id", "")))),
    }


@app.get("/api/results")
def get_results_summary(db: Session = Depends(get_db)):
    return run_batch_evaluation(db)


@app.post("/api/invoices/{invoice_id}/simulate_reply")
def simulate_customer_reply(invoice_id: int, payload: ReplyPayload, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        extracted = promise_extraction.extract_promise(
            db,
            invoice_id,
            payload.text,
            invoice.amount,
        )
        db.expire(invoice, ["promises"])
        extraction = db.query(Ledger).filter(
            Ledger.invoice_id == invoice_id, Ledger.event_type == "promise_extracted"
        ).order_by(Ledger.id.desc()).first()
        raw = (extraction.payload or {}).get("raw", {}) if extraction else {}
        return {
            "status": "success", "message": "Promise extracted and logged to ledger." if extracted else "Reply logged, but no concrete commitment found.",
            "extraction": raw,
            "needs_review": bool(invoice.needs_review),
            "promises": [{"id": item.id, "amount": item.amount, "promised_date": item.promised_date.isoformat() if item.promised_date else None, "confidence": item.confidence.value, "status": item.status.value} for item in extracted],
        }
    except HTTPException:
        db.commit()
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/simulate/reply")
def simulate_reply(payload: SimulateReplyPayload, db: Session = Depends(get_db)):
    return simulate_customer_reply(payload.invoice_id, payload, db)


@app.post("/api/invoices/{invoice_id}/sync-payment")
def sync_invoice_payment(invoice_id: int, payload: PaymentPayload, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    amount_paid = payload.amount_paid
    source = "demo_manual"
    provider_status = "manual"
    if amount_paid is None:
        if invoice.razorpay_payment_link_id:
            remote = razorpay_client.fetch_payment_link(invoice.razorpay_payment_link_id)
        else:
            remote = razorpay_client.check_payment_status(invoice.razorpay_invoice_id)
        amount_paid = remote.get("amount_paid", 0.0)
        provider_status = remote.get("status", "unknown")
        source = "razorpay_sync"
    payments.apply_payment(db, invoice, amount_paid, source)
    reliability.score_customer(invoice.customer_id, db, persist=True)
    refreshed_status = invoice.status.value
    message = (
        f"Razorpay sync complete: {invoice.amount_paid:.2f} received."
        if invoice.amount_paid > 0
        else "Razorpay sync complete: no payment has been reported by the provider yet."
    )
    return {
        "status": "success",
        "message": message,
        "invoice_id": invoice.id,
        "amount_paid": invoice.amount_paid,
        "invoice_status": refreshed_status,
        "provider_status": provider_status,
        "next_action": _next_action(db, invoice),
        "next_message": _next_message(db, invoice),
    }


@app.post("/api/jobs/run_escalations", response_model=CronRunResponse)
def trigger_escalation_cron(db: Session = Depends(get_db)):
    unpaid_invoices = (
        db.query(Invoice)
        .filter(Invoice.status.in_([InvoiceStatus.unpaid, InvoiceStatus.partially_paid]))
        .order_by(Invoice.due_date.asc(), Invoice.amount.desc())
        .limit(config.MAX_CRON_INVOICES_PER_RUN)
        .all()
    )
    processed = 0
    updated_invoices = []
    run_at = demo_now().isoformat()

    for inv in unpaid_invoices:
        before_stage = inv.current_stage.value if inv.current_stage else "none"
        before_status = inv.status.value
        escalation.evaluate_and_escalate(db, inv.id)
        refreshed = db.query(Invoice).filter(Invoice.id == inv.id).first()
        processed += 1

        if not refreshed:
            continue

        after_stage = refreshed.current_stage.value if refreshed.current_stage else "none"
        after_status = refreshed.status.value
        if before_stage != after_stage or before_status != after_status:
            updated_invoices.append({
                "invoice_id": inv.id,
                "previous_stage": before_stage,
                "new_stage": after_stage,
                "previous_status": before_status,
                "new_status": after_status,
            })

    return CronRunResponse(
        status="success",
        message=f"Evaluated {processed} invoices for escalation.",
        processed=processed,
        updated_invoices=updated_invoices,
        run_at=run_at,
    )


@app.get("/demo/clock")
def get_demo_clock():
    return {"now": demo_now().isoformat()}


def _wipe_demo_data(db: Session) -> None:
    demo_invoices = select(Invoice.id).where(Invoice.customer_id >= 10000)
    db.query(Promise).filter(Promise.invoice_id.in_(demo_invoices)).delete(synchronize_session=False)
    db.query(Ledger).filter(Ledger.invoice_id.in_(demo_invoices)).delete(synchronize_session=False)
    db.query(CustomerReliability).filter(CustomerReliability.customer_id >= 10000).delete(synchronize_session=False)
    db.query(Invoice).filter(Invoice.customer_id >= 10000).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.id >= 10000).delete(synchronize_session=False)
    db.commit()


def _seed_demo_data() -> None:
    from backend.data.seed_manual_demo import seed_manual_demo
    seed_manual_demo()


@app.post("/demo/seed")
def seed_demo():
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        _wipe_demo_data(db)
    finally:
        db.close()
    reset_demo_clock()
    _seed_demo_data()
    return {"status": "success", "message": "Demo data seeded.", "now": demo_now().isoformat()}


@app.post("/demo/reset")
def reset_demo():
    return seed_demo()


@app.post("/demo/advance-clock")
def advance_demo(payload: AdvanceClockPayload):
    if payload.days not in (1, 7):
        raise HTTPException(status_code=400, detail="Demo clock accepts only 1 or 7 days.")
    current_time = advance_demo_clock(payload.days)
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        invoices = db.query(Invoice).filter(
            Invoice.customer_id >= 10000,
            Invoice.status.in_([InvoiceStatus.unpaid, InvoiceStatus.partially_paid])
        ).limit(config.MAX_CRON_INVOICES_PER_RUN).all()
        for invoice in invoices:
            escalation.evaluate_and_escalate(db, invoice.id)
    finally:
        db.close()
    return {"status": "success", "message": f"Demo clock advanced by {payload.days} day(s).", "now": current_time.isoformat()}


frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="frontend-assets")


@app.get("/{full_path:path}")
def frontend_index(full_path: str):
    index = os.path.join(frontend_dist, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "CHASR API is running. Build the frontend bundle to serve the UI."}
