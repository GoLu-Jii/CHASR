"""Reliability feature computation and trained-model inference."""

import os

import joblib
import pandas as pd
from datetime import datetime

from sqlalchemy import func

from backend.models import CustomerReliability, Ledger, LedgerEventType, Promise, PromiseStatus

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "reliability_model.joblib")
_model = None


def _features(customer_id, db):
    """Compute inference features from persisted events, never from constants."""
    global _model
    promises = (
        db.query(Promise)
        .join(Promise.invoice)
        .filter(Promise.invoice.has(customer_id=customer_id))
        .all()
    )
    if not promises:
        return None

    total = len(promises)
    kept_full = sum(p.status == PromiseStatus.kept_full for p in promises)
    kept_partial = sum(p.status == PromiseStatus.kept_partial for p in promises)
    broken = sum(p.status == PromiseStatus.broken for p in promises)
    kept_rate = (kept_full + kept_partial) / total
    broken_rate = broken / total
    dated_promises = [p for p in promises if p.promised_date and p.invoice and p.invoice.due_date]
    avg_days_late = (
        sum(max(0, (p.promised_date - p.invoice.due_date).days) for p in dated_promises) / len(dated_promises)
        if dated_promises else 0.0
    )
    invoice_ids = [p.invoice_id for p in promises]
    replies = db.query(Ledger).filter(
        Ledger.invoice_id.in_(invoice_ids), Ledger.event_type == LedgerEventType.reply_received
    ).count() if invoice_ids else 0
    escalations = db.query(Ledger).filter(
        Ledger.invoice_id.in_(invoice_ids), Ledger.event_type == LedgerEventType.escalation_sent
    ).count() if invoice_ids else 0
    responsiveness = min(1.0, replies / max(1, escalations))
    return {
        "total": total, "kept_full": kept_full, "kept_partial": kept_partial,
        "broken": broken, "kept_rate": kept_rate, "broken_rate": broken_rate,
        "avg_days_late": avg_days_late, "responsiveness": responsiveness,
    }


def score_customer(customer_id, db, persist: bool = False) -> float:
    """Return a bounded score; cold-start customers intentionally receive 0.5."""
    global _model
    features = _features(customer_id, db)
    if features is None:
        return 0.5

    if _model is None and os.path.exists(MODEL_PATH):
        _model = joblib.load(MODEL_PATH)
    if _model is not None:
        model_features = pd.DataFrame([[
            features["total"], features["kept_full"], features["kept_partial"],
            features["broken"], features["kept_rate"], features["broken_rate"],
            features["avg_days_late"],
        ]], columns=[
            "hist_total_promises", "hist_kept_full", "hist_kept_partial",
            "hist_broken", "hist_kept_rate", "hist_broken_rate", "hist_avg_days_late",
        ])
        score = float(_model.predict_proba(model_features)[0][1])
    else:
        score = features["kept_rate"]

    # Responsiveness is a live feature not present in the already-trained
    # seven-column model. Apply only a small bounded calibration until the next
    # offline retraining incorporates it directly.
    score = score * 0.9 + features["responsiveness"] * 0.1
    score = round(max(0.0, min(1.0, score)), 2)
    if persist:
        db.add(CustomerReliability(
            customer_id=customer_id, computed_at=datetime.utcnow(),
            total_promises=features["total"], kept_full=features["kept_full"],
            kept_partial=features["kept_partial"], broken=features["broken"],
            kept_full_rate=features["kept_rate"], broken_rate=features["broken_rate"],
            avg_days_late=features["avg_days_late"], score=score,
        ))
        db.commit()
    return score
