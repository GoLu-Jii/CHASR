"""Reliability feature computation and trained-model inference."""

import os

import joblib

from backend.models import Promise, PromiseStatus

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "reliability_model.joblib")
_model = None


def score_customer(customer_id, db) -> float:
    """Return a bounded score, using history when available and 0.5 otherwise."""
    global _model
    promises = (
        db.query(Promise)
        .join(Promise.invoice)
        .filter(Promise.invoice.has(customer_id=customer_id))
        .all()
    )
    if not promises:
        return 0.5

    total = len(promises)
    kept_full = sum(p.status == PromiseStatus.kept_full for p in promises)
    kept_partial = sum(p.status == PromiseStatus.kept_partial for p in promises)
    broken = sum(p.status == PromiseStatus.broken for p in promises)
    kept_rate = (kept_full + kept_partial) / total
    broken_rate = broken / total

    if _model is None and os.path.exists(MODEL_PATH):
        _model = joblib.load(MODEL_PATH)
    if _model is not None:
        features = [[total, kept_full, kept_partial, broken, kept_rate, broken_rate, 0.0]]
        score = float(_model.predict_proba(features)[0][1])
    else:
        score = kept_rate
    return round(max(0.0, min(1.0, score)), 2)
