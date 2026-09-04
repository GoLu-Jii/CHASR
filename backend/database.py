# backend/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend.models import Base
    Base.metadata.create_all(bind=engine)
    # This MVP predates migrations. Keep development databases compatible with
    # the two additive fields introduced for the auditable payment flow.
    if DATABASE_URL.startswith("sqlite"):
        from sqlalchemy import text
        with engine.begin() as connection:
            columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(invoices)"))
            }
            if "contact_count" not in columns:
                connection.execute(text("ALTER TABLE invoices ADD COLUMN contact_count INTEGER NOT NULL DEFAULT 0"))
            if "razorpay_payment_link_id" not in columns:
                connection.execute(text("ALTER TABLE invoices ADD COLUMN razorpay_payment_link_id VARCHAR"))
