"""Truthful held-out evaluation used by the results screen.

The historical synthetic data records payment outcomes, not counterfactual
outcomes for two different reminder policies.  We therefore report observed
recovery once and compare the *targeting* quality of CHASR with a fixed-date
baseline.  We do not invent a causal recovery uplift.
"""

import random

import joblib
from sklearn.metrics import precision_score, recall_score

from backend import config
from backend.database import engine
from backend.ml.train_reliability_model import MODEL_PATH, load_and_engineer_features
from backend.models import Invoice, Promise, PromiseStatus


FEATURE_COLUMNS = [
    "hist_total_promises", "hist_kept_full", "hist_kept_partial",
    "hist_broken", "hist_kept_rate", "hist_broken_rate", "hist_avg_days_late",
]


def run_batch_evaluation(db, limit: int = 50) -> dict:
    try:
        df = load_and_engineer_features(engine)
    except ValueError:
        return _empty_result()
    customer_ids = sorted(df["customer_id"].unique().tolist())
    random.Random(42).shuffle(customer_ids)
    split = int(len(customer_ids) * config.TRAIN_FRACTION)
    held_out = set(customer_ids[split:])
    test_df = df[df["customer_id"].isin(held_out)].copy()
    if test_df.empty:
        return _empty_result()

    model = joblib.load(MODEL_PATH)
    test_df["prediction"] = model.predict(test_df[FEATURE_COLUMNS])
    test_df["probability"] = model.predict_proba(test_df[FEATURE_COLUMNS])[:, 1]
    precision = precision_score(test_df["target_is_kept"], test_df["prediction"], zero_division=0)
    recall = recall_score(test_df["target_is_kept"], test_df["prediction"], zero_division=0)

    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id.in_(held_out))
        .order_by(Invoice.due_date.desc())
        .limit(limit)
        .all()
    )
    observed_recovered = round(sum(float(invoice.amount_paid or 0) for invoice in invoices), 2)
    baseline_targets = sorted(invoices, key=lambda invoice: invoice.due_date)[: min(20, len(invoices))]
    adaptive_targets = sorted(invoices, key=lambda invoice: _invoice_risk(invoice, test_df), reverse=True)[: min(20, len(invoices))]

    exceptions = []
    broken = (
        db.query(Promise)
        .join(Invoice)
        .filter(Invoice.customer_id.in_(held_out), Promise.status == PromiseStatus.broken)
        .order_by(Invoice.amount.desc())
        .limit(8)
        .all()
    )
    for promise in broken:
        exceptions.append({
            "invoice_id": promise.invoice_id,
            "customer": promise.invoice.customer.name,
            "amount": float(promise.invoice.amount),
            "reason": "Promise was broken in the held-out history",
        })

    return {
        "batch_size": len(invoices),
        "observed_recovered_inr": observed_recovered,
        "model_recovered_inr": observed_recovered,
        "baseline_recovered_inr": observed_recovered,
        "precision": round(float(precision), 3),
        "recall": round(float(recall), 3),
        "improvement_pct": 0.0,
        "adaptive_target_invoice_ids": [invoice.id for invoice in adaptive_targets],
        "baseline_target_invoice_ids": [invoice.id for invoice in baseline_targets],
        "exceptions": exceptions,
        "methodology": "Observed held-out recovery is shared because this historical dataset has no counterfactual reminder-policy outcome. The comparison measures targeting, not an invented causal uplift.",
    }


def _invoice_risk(invoice, test_df) -> float:
    promise = next((p for p in invoice.promises if p.status in {PromiseStatus.broken, PromiseStatus.pending}), None)
    if not promise:
        return 0.0
    row = test_df[test_df["promise_id"] == promise.id]
    return 1 - float(row.iloc[0]["probability"]) if not row.empty else 0.5


def _empty_result():
    return {"batch_size": 0, "observed_recovered_inr": 0.0, "model_recovered_inr": 0.0, "baseline_recovered_inr": 0.0, "precision": 0.0, "recall": 0.0, "improvement_pct": 0.0, "adaptive_target_invoice_ids": [], "baseline_target_invoice_ids": [], "exceptions": [], "methodology": "No synthetic history is available. Run the generator and train the model first."}
