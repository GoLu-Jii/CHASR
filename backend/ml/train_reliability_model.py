# backend/ml/train_reliability_model.py

import os
import random
import joblib
import pandas as pd
from sqlalchemy import text
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, roc_auc_score, classification_report

from backend import config

os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
MODEL_PATH = os.path.join(os.path.dirname(__file__), "reliability_model.joblib")

def load_and_engineer_features(engine):
    """
    For any promise N, features come exclusively from that SAME customer's
    promises that happened chronologically BEFORE N — no leakage.
    """
    print("Loading data and engineering temporal features...")

    query = text("""
        SELECT
            p.id as promise_id,
            i.customer_id,
            i.amount as invoice_amount,
            i.due_date,
            p.promised_date,
            p.status
        FROM promises p
        JOIN invoices i ON p.invoice_id = i.id
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    if df.empty:
        raise ValueError("No promises found in database. Run synthetic generator first.")

    df["due_date"] = pd.to_datetime(df["due_date"])
    df["promised_date"] = pd.to_datetime(df["promised_date"])

    features_list = []

    for customer_id, group in df.groupby("customer_id"):
        # Sort by actual chronological order (due_date)
        group = group.sort_values("due_date").reset_index(drop=True)

        hist_kept_full = 0
        hist_kept_partial = 0
        hist_broken = 0
        hist_days_late_sum = 0

        for _, row in group.iterrows():
            total_promises = hist_kept_full + hist_kept_partial + hist_broken
            is_kept = 1 if row["status"] in ["kept_full", "kept_partial"] else 0

            features_list.append({
                "promise_id": row["promise_id"],
                "customer_id": row["customer_id"],
                "hist_total_promises": total_promises,
                "hist_kept_full": hist_kept_full,
                "hist_kept_partial": hist_kept_partial,
                "hist_broken": hist_broken,
                "hist_kept_rate": ((hist_kept_full + hist_kept_partial) / total_promises) if total_promises > 0 else 0.0,
                "hist_broken_rate": (hist_broken / total_promises) if total_promises > 0 else 0.0,
                "hist_avg_days_late": (hist_days_late_sum / total_promises) if total_promises > 0 else 0.0,
                "target_is_kept": is_kept,
            })

            if row["status"] == "kept_full":
                hist_kept_full += 1
            elif row["status"] == "kept_partial":
                hist_kept_partial += 1
            elif row["status"] == "broken":
                hist_broken += 1

            if pd.notnull(row["promised_date"]) and pd.notnull(row["due_date"]):
                days_late = (row["promised_date"] - row["due_date"]).days
                hist_days_late_sum += max(0, days_late)

    return pd.DataFrame(features_list)

def train_and_evaluate():
    from backend.database import engine

    df = load_and_engineer_features(engine)

    unique_customers = df["customer_id"].unique().tolist()
    random.seed(42)
    random.shuffle(unique_customers)

    split_idx = int(len(unique_customers) * config.TRAIN_FRACTION)
    train_customers = set(unique_customers[:split_idx])
    test_customers = set(unique_customers[split_idx:])

    train_df = df[df["customer_id"].isin(train_customers)]
    test_df = df[df["customer_id"].isin(test_customers)]

    # REMOVED invoice_amount. It is random noise preventing convergence.
    feature_cols = [
        "hist_total_promises", "hist_kept_full",
        "hist_kept_partial", "hist_broken", "hist_kept_rate",
        "hist_broken_rate", "hist_avg_days_late",
    ]

    X_train, y_train = train_df[feature_cols], train_df["target_is_kept"]
    X_test, y_test = test_df[feature_cols], test_df["target_is_kept"]

    print(f"\nDataset Split: {len(train_customers)} Train Customers, {len(test_customers)} Test Customers")
    print(f"Row Counts: {len(X_train)} Train Promises, {len(X_test)} Test Promises")

    print("\nTraining Pipeline (StandardScaler + LogisticRegression)...")
    # ADDED Pipeline with StandardScaler and class_weight='balanced'
    model = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42))
    ])
    
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)

    print("\n--- Model Evaluation (Held-out Customers) ---")
    print(f"ROC-AUC:   {roc_auc:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Broken (0)", "Kept (1)"]))

    joblib.dump(model, MODEL_PATH)
    print(f"\nModel successfully saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_and_evaluate()