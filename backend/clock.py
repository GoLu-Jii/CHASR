"""Small persisted virtual clock used by the repeatable demo."""

from datetime import datetime, timedelta

from sqlalchemy import text

from backend.database import engine


def _ensure_state() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS demo_state "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), offset_days INTEGER NOT NULL)"
        ))
        connection.execute(text(
            "INSERT OR IGNORE INTO demo_state (id, offset_days) VALUES (1, 0)"
        ))


def now() -> datetime:
    _ensure_state()
    with engine.connect() as connection:
        offset = connection.execute(
            text("SELECT offset_days FROM demo_state WHERE id = 1")
        ).scalar_one()
    return datetime.utcnow() + timedelta(days=int(offset))


def advance(days: int) -> datetime:
    if days < 0:
        raise ValueError("Demo clock cannot move backwards.")
    _ensure_state()
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE demo_state SET offset_days = offset_days + :days "
                "WHERE id = 1"
            ),
            {"days": days},
        )
    return now()


def reset() -> datetime:
    _ensure_state()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE demo_state SET offset_days = 0 WHERE id = 1")
        )
    return now()
