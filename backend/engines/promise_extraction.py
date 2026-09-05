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


def _parse_json_response(raw_content: str) -> dict:
    """Parse the model's reply into a dict, tolerating code fences or prose wraps.

    JSON mode makes stray prose unlikely, but a single robust parser keeps the
    promise pipeline from discarding a valid commitment on presentation noise.
    """
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        # Strip a leading fence (and optional language tag) plus a closing fence.
        cleaned = cleaned.split("```", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    if cleaned:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Recover the first balanced JSON object if the model wrapped it in prose.
    start = cleaned.find("{")
    while start != -1:
        for end in range(start + 1, len(cleaned) + 1):
            candidate = cleaned[start:end]
            if not candidate.startswith("{"):
                break
            if candidate.count("{") == candidate.count("}") and candidate.count("[") == candidate.count("]"):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break
        start = cleaned.find("{", start + 1)

    return {"has_commitment": False, "commitments": []}

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

    # Relative wording (for example, "next Wednesday") has a meaning only at
    # the moment the customer sent it.  Re-submitting the exact same reply on a
    # later virtual day must not turn it into a new, postponed commitment.
    # Return the original record instead; a new commitment needs new customer
    # language and therefore a distinct source text.
    existing = (
        session.query(Promise)
        .filter(Promise.invoice_id == invoice_id, Promise.source_text == reply_text)
        .order_by(Promise.id.asc())
        .all()
    )
    if existing:
        session.commit()
        return existing

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
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"The total invoice amount is {invoice_amount:.2f}. "
                        f"The amount of the invoice already received is 0.00. "
                        f"The remaining balance to be collected is {invoice_amount:.2f}. "
                        f"Today's reference date is {current_date}. "
                        "You extract payment commitments from a customer reply into strict JSON. "
                        "Rules: (1) Extract only commitments explicitly supported by the reply; "
                        "never infer an amount, date, or promise from intent, optimism, a dispute, "
                        "or a request for more time. (2) 'we will try', 'soon', 'when cash flow "
                        "improves' may be a vague commitment but must keep amount and/or date null "
                        "when those facts are not stated. (3) Resolve explicit percentages and "
                        "relative dates against the invoice amount and the reference date; for a "
                        "stated remainder, compute only the remainder of other explicit tranches in "
                        "the same reply. (4) Round every amount to 2 decimal places (rupees). "
                        "(5) Never let a commitment amount exceed the remaining balance; if it would, "
                        "cap it at the remaining balance and set confidence to 'soft'. "
                        "(6) A promised_date must be an ISO date 'YYYY-MM-DD' and only when the "
                        "customer states a concrete date; otherwise null. (7) If a commitment merely "
                        "restates an earlier promise on the same invoice, do NOT reinterpret its "
                        "relative date into a newer future date; reuse the originally promised date or "
                        "leave it null. (8) Return one object per distinct tranche, exactly matching "
                        "this JSON schema: "
                        "{\"has_commitment\": boolean, \"commitments\": "
                        "[{\"amount\": number or null, \"promised_date\": string or null, "
                        "\"confidence\": \"firm\"|\"soft\"|\"vague\"}]}. "
                        "Return only this JSON object, with no other text. Set has_commitment to "
                        "false and commitments to [] when there is no actual commitment."
                    ),
                },
                {"role": "user", "content": reply_text},
            ],
            temperature=0,
            max_tokens=2048,
        )

        try:
            raw_content = response.choices[0].message.content or ""
            result = _parse_json_response(raw_content)
        except (TypeError, ValueError, json.JSONDecodeError):
            result = {"has_commitment": False, "commitments": []}
    except Exception as exc:
        raise HTTPException(
            status_code=429,
            detail=f"LLM API Error: {exc}",
        ) from exc

    if not isinstance(result, dict):
        result = {"has_commitment": False, "commitments": []}
    commitments = result.get("commitments")
    if not isinstance(commitments, list):
        commitments = []
    # Preserve the model output in the audit record, while accepting only the
    # narrow structure the rest of the system understands.  A contradictory
    # response is treated conservatively: `has_commitment: false` wins.
    has_commitment = bool(result.get("has_commitment"))
    result = {
        "has_commitment": has_commitment,
        "commitments": commitments if has_commitment else [],
    }
    commitments = result["commitments"]
    ledger_engine.append_entry(session, invoice_id, LedgerEventType.promise_extracted, {"raw": result})

    created = []
    for c in commitments:
        if not isinstance(c, dict):
            continue
        confidence_value = c.get("confidence", "vague")
        if confidence_value not in {item.value for item in PromiseConfidence}:
            confidence_value = "vague"
        amount = c.get("amount")
        if not isinstance(amount, (int, float)) or amount <= 0 or amount > invoice_amount:
            amount = None
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

        duplicate = session.query(Promise).filter(
            Promise.invoice_id == invoice_id,
            Promise.source_text == reply_text,
            Promise.amount == amount,
            Promise.promised_date == promised_date,
            Promise.status == PromiseStatus.pending,
        ).first()
        if duplicate:
            created.append(duplicate)
            continue

        promise = Promise(
            invoice_id=invoice_id,
            ledger_entry_id=reply_entry.id,
            amount=amount,
            promised_date=promised_date,
            confidence=PromiseConfidence(confidence_value),
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
