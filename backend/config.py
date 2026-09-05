# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chasr.db")

# §9.3 — kept / partial / broken thresholds
KEPT_MIN_PCT = 0.95
# A stated payment date is a firm operational deadline in the demo and in the
# scheduler.  Once the virtual day passes it, CHASR evaluates the outcome
# immediately instead of quietly extending the commitment.
KEPT_GRACE_DAYS = 0
PARTIAL_MIN_PCT = 0.30
PARTIAL_GRACE_DAYS = 7

# Escalation ladder cutoffs (days overdue).  The engine adjusts these within the
# bounded low/high-reliability windows below; it never asks an LLM to decide.
NUDGE_AFTER_DAYS = 0
FIRM_AFTER_DAYS = 15
FORMAL_AFTER_DAYS = 30
LOW_RELIABILITY_THRESHOLD = 0.40
# Scores are probability-like model outputs with a small responsiveness
# calibration.  0.65 reliably separates the demonstrated promise-keepers
# from neutral accounts while retaining a meaningful middle band.
HIGH_RELIABILITY_THRESHOLD = 0.65
LOW_RELIABILITY_FIRM_AFTER_DAYS = 7
LOW_RELIABILITY_FORMAL_AFTER_DAYS = 21
HIGH_RELIABILITY_FIRM_AFTER_DAYS = 20
HIGH_RELIABILITY_FORMAL_AFTER_DAYS = 35
RECONTACT_INTERVAL_DAYS = 7

# §9.4 — stopping rule
OBSERVATION_WINDOW_DAYS = 10
MAX_AUTOMATED_CONTACTS = 6

# Demo-safe batch limit: keep the cron route bounded so it finishes in ~20–30s
# even if the database grows beyond the demo size.
MAX_CRON_INVOICES_PER_RUN = 25

# §9.2
TRAIN_FRACTION = 0.70
