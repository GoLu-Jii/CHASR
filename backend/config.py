# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chasr.db")

# §9.3 — kept / partial / broken thresholds
KEPT_MIN_PCT = 0.95
KEPT_GRACE_DAYS = 2
PARTIAL_MIN_PCT = 0.30
PARTIAL_GRACE_DAYS = 7

# Escalation ladder cutoffs (days overdue) — placeholder until reliability.py replaces this
NUDGE_AFTER_DAYS = 0
FIRM_AFTER_DAYS = 15
FORMAL_AFTER_DAYS = 30

# §9.4 — stopping rule
OBSERVATION_WINDOW_DAYS = 10
MAX_AUTOMATED_CONTACTS = 6

# §9.2
TRAIN_FRACTION = 0.70