# backend/engines/promise_extraction.py

import json
from datetime import datetime

from fastapi import HTTPException
from groq import Groq

from backend import config
from backend.clock import now
from backend.engines import ledger as ledger_engine
from backend.models import Invoice, LedgerEventType, Promise, PromiseConfidence, PromiseStatus


def get_groq_client():
    if not config.GROQ_API_KEY:
        return None
    # Groq's SDK appends /openai/v1 itself; keep the base at the API host.
    return Groq(api_key=config.GROQ_API_KEY, base_url="https://api.groq.com")

def extract_promise(
    session,
    invoice_id: int,
    reply_text: str,
    invoice_amount: float = 0.0,
) -> list[Promise]:
    if session is None:
        return []

    reply_entry = ledger_engine.append_entry(
        session, invoice_id, LedgerEventType.reply_received, {"text": reply_text}
    )
    if not config.GROQ_API_KEY:
        session.commit()
        raise HTTPException(status_code=429, detail="LLM API Error: GROQ_API_KEY is not configured")

    try:
        client = get_groq_client()
        if not client:
            return []

        current_date = now().date().isoformat()
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"The total invoice amount is {invoice_amount}. "
                        f"Today's reference date is {current_date}. "
                        "Extract payment commitments from the customer reply. "
                        "Resolve percentages and relative amounts. Resolve every "
                        "relative date to strict YYYY-MM-DD. Return only one valid JSON "
                        "matching this schema: {\"has_commitment\": boolean, "
                        "\"commitments\": [{\"amount\": number or null, "
                        "\"promised_date\": string or null, \"confidence\": "
                        "\"firm\"|\"soft\"|\"vague\"}]}."
                    ),
                },
                {"role": "user", "content": reply_text},
            ],
            temperature=0,
            max_tokens=2048,
        )

        try:
            raw_content = response.choices[0].message.content or ""
            cleaned_content = raw_content.replace("```json", "").replace("```", "").strip()
            result = json.loads(cleaned_content)
        except (TypeError, ValueError, json.JSONDecodeError):
            result = {"has_commitment": False, "commitments": []}
    except Exception as exc:
        raise HTTPException(
            status_code=429,
            detail=f"LLM API Error: {exc}",
        ) from exc

    ledger_engine.append_entry(session, invoice_id, LedgerEventType.promise_extracted, {"raw": result})

    created = []
    for c in result.get("commitments", []):
        promised_date = None
        promised_date_value = c.get("promised_date")
        if promised_date_value:
            try:
                promised_date = datetime.strptime(
                    promised_date_value,
                    "%Y-%m-%d",
                )
            except (TypeError, ValueError):
                promised_date = None

        has_concrete_date = promised_date is not None

        promise = Promise(
            invoice_id=invoice_id,
            ledger_entry_id=reply_entry.id,
            amount=c.get("amount"),
            promised_date=promised_date,
            confidence=PromiseConfidence(c["confidence"]),
            status=PromiseStatus.pending,
            source_text=reply_text,
        )
        session.add(promise)
        created.append(promise)

        if not has_concrete_date:
            invoice = session.query(Invoice).filter_by(id=invoice_id).first()
            if invoice:
                invoice.needs_review = True

    session.commit()
    return created
