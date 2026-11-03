"""Conservative, inspectable structured-field verifier; not a general NLI engine."""
from __future__ import annotations
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from .models import Claim, AnswerType, SourceSnapshot, SupportFinding
from .passages import extract_passages, verify_passage

DATE_FORMATS = ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d")


def canonical(value: str, kind: AnswerType) -> str:
    v = value.strip().rstrip(".,; ")
    if kind == AnswerType.DATE:
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        raise ValueError(f"unrecognized exact date: {v}")
    if kind == AnswerType.NUMBER:
        try:
            return str(Decimal(v.replace(",", "")).normalize())
        except InvalidOperation as exc:
            raise ValueError(f"unrecognized number: {v}") from exc
    return v.casefold() if kind == AnswerType.IDENTIFIER else v


def find_support(claim: Claim, snapshots: list[SourceSnapshot]) -> list[SupportFinding]:
    if not claim.evidence_pattern:
        return []  # TEXT / unconfigured claims cannot be auto-certified.
    if len(claim.evidence_pattern) > 500:
        raise ValueError("evidence regex too long")
    regex = re.compile(claim.evidence_pattern, re.IGNORECASE)
    if "value" not in regex.groupindex:
        raise ValueError("evidence regex needs named capture group 'value'")
    desired = canonical(claim.expected_value, claim.answer_type)
    findings: list[SupportFinding] = []
    for snap in snapshots:
        for p in extract_passages(snap):
            if not verify_passage(p, snap):
                raise ValueError("fabricated or invalid passage")
            for match in regex.finditer(p.text):
                # Reject association with an unrelated subject unless curator validated document subject.
                known_subject = snap.subject_reviewed and snap.subject and snap.subject.casefold() == claim.subject.casefold()
                mentioned_subject = claim.subject.casefold() in p.text.casefold()
                if not (known_subject or mentioned_subject):
                    continue
                # Explicit negation can invert the asserted value; we abstain rather than guessing.
                prefix = p.text[max(0, match.start()-18):match.start()].lower()
                if re.search(r"\b(not|never|incorrectly|falsely)\s*$", prefix):
                    relation, reason, value = "UNCERTAIN", "negated or qualified evidence", None
                else:
                    value = match.group("value").strip()
                    try:
                        observed = canonical(value, claim.answer_type)
                        relation = "SUPPORTS" if observed == desired else "CONTRADICTS"
                        reason = "explicit pattern-backed field comparison"
                    except ValueError:
                        relation, reason = "UNCERTAIN", "could not normalize extracted value"
                findings.append(SupportFinding(source_id=snap.source_id, snapshot_id=snap.snapshot_id,
                    passage_id=p.passage_id, relation=relation, extracted_value=value,
                    quoted_text=p.text[match.start():match.end()], rationale=reason))
    return findings
