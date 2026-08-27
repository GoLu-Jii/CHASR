# backend/engines/ledger.py

import hashlib
import json
from datetime import datetime
from backend.models import Ledger, LedgerEventType

def _generate_hash(prev_hash: str, payload: dict, timestamp: str) -> str:
    """Generates a SHA-256 hash for the new ledger entry."""
    # Ensure consistent JSON formatting for hashing
    payload_str = json.dumps(payload, sort_keys=True)
    block_string = f"{prev_hash}|{payload_str}|{timestamp}"
    return hashlib.sha256(block_string.encode()).hexdigest()

def append_entry(session, invoice_id: int, event_type: LedgerEventType, payload: dict) -> Ledger:
    """
    The ONLY way data is added to the ledger. 
    Finds the last hash for this invoice and chains the new one.
    """
    # Find the most recent entry for this invoice to get the prev_hash
    last_entry = session.query(Ledger).filter(
        Ledger.invoice_id == invoice_id
    ).order_by(Ledger.id.desc()).first()

    prev_hash = last_entry.hash if last_entry else ("0" * 64)
    timestamp = datetime.utcnow().isoformat()
    
    new_hash = _generate_hash(prev_hash, payload, timestamp)

    new_entry = Ledger(
        invoice_id=invoice_id,
        event_type=event_type,
        payload=payload,
        created_at=datetime.fromisoformat(timestamp),
        prev_hash=prev_hash,
        hash=new_hash
    )
    
    session.add(new_entry)
    session.commit()
    return new_entry

def verify_chain(session, invoice_id: int) -> bool:
    """
    Cryptographically verifies that no ledger entries for this invoice 
    have been tampered with or deleted.
    """
    entries = session.query(Ledger).filter(
        Ledger.invoice_id == invoice_id
    ).order_by(Ledger.id.asc()).all()

    if not entries:
        return True

    expected_prev_hash = "0" * 64
    for entry in entries:
        # 1. Check if the link to the previous block is broken
        if entry.prev_hash != expected_prev_hash:
            return False
            
        # 2. Recompute the hash to ensure the payload/timestamp wasn't altered
        timestamp_str = entry.created_at.isoformat()
        recomputed_hash = _generate_hash(entry.prev_hash, entry.payload, timestamp_str)
        
        if recomputed_hash != entry.hash:
            return False
            
        expected_prev_hash = entry.hash

    return True