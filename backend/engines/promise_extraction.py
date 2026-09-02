# backend/engines/promise_extraction.py

import json
from datetime import datetime

from groq import Groq

from backend import config
from backend.engines import ledger as ledger_engine
from backend.models import Invoice, LedgerEventType, Promise, PromiseConfidence, PromiseStatus


def get_groq_client():
    if not config.GROQ_API_KEY:
        return None
    return Groq(api_key=config.GROQ_API_KEY)

# Groq uses the OpenAI tool-calling format (type, function, parameters)
EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_promise",
        "description": "Extract structured payment commitments from a customer's reply about an overdue invoice. Never invent an amount or date that wasn't actually stated.",
        "parameters": {
            "type": "object",
            "properties": {
                "has_commitment": {"type": "boolean"},
                "commitments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": ["number", "null"]},
                            "promised_date": {"type": ["string", "null"], "description": "ISO date (YYYY-MM-DD), or null if none was actually stated"},
                            "confidence": {"type": "string", "enum": ["firm", "soft", "vague"]}
                        },
                        "required": ["confidence"]
                    }
                }
            },
            "required": ["has_commitment", "commitments"]
        }
    }
}

def extract_promise(session, invoice_id: int, reply_text: str) -> list[Promise]:
    if not config.GROQ_API_KEY or session is None:
        return []

    reply_entry = ledger_engine.append_entry(
        session, invoice_id, LedgerEventType.reply_received, {"text": reply_text}
    )

    try:
        client = get_groq_client()
        if not client:
            return []

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{
                "role": "user",
                "content": f'Today\'s date: {datetime.utcnow().date().isoformat()}\nCustomer reply regarding an overdue invoice:\n"{reply_text}"'
            }],
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "function", "function": {"name": "extract_promise"}},
            temperature=0,
            max_tokens=512,
        )

        tool_calls = getattr(response.choices[0].message, "tool_calls", None) or []
        if not tool_calls:
            return []

        result = json.loads(tool_calls[0].function.arguments)
    except Exception:
        return []

    ledger_engine.append_entry(session, invoice_id, LedgerEventType.promise_extracted, {"raw": result})

    created = []
    for c in result.get("commitments", []):
        has_concrete_date = bool(c.get("promised_date"))

        promise = Promise(
            invoice_id=invoice_id,
            ledger_entry_id=reply_entry.id,
            amount=c.get("amount"),
            promised_date=datetime.fromisoformat(c["promised_date"]) if has_concrete_date else None,
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
