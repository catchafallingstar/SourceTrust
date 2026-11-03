"""Integrated verification, conservative evidence sufficiency, budget and report."""
from __future__ import annotations
from uuid import uuid4
from .models import Claim, VerificationConfig, VerificationReport, SourceSnapshot, SourceRole
from .storage import read_snapshot
from .verifier import find_support, canonical
from .lineage import inspect_lineage
from .retrieval import ArchiveRetriever


def _assessment(claim, sources, findings, mode):
    # Temporal snapshots alone cannot establish time-sensitive validity.
    # A dedicated as-of/version checker must be added before such claims can pass.
    if claim.as_of_date:
        return "NOT_CHECKABLE", "HUMAN_REVIEW", None, "as-of temporal checking not implemented in this prototype"
    by_id = {s.source_id: s for s in sources}
    supports = [f for f in findings if f.relation == "SUPPORTS"]
    contradicts = [f for f in findings if f.relation == "CONTRADICTS"]
    authoritative_s = [f for f in supports if by_id[f.source_id].role == SourceRole.ORIGINAL_RECORD and by_id[f.source_id].identity_reviewed]
    authoritative_c = [f for f in contradicts if by_id[f.source_id].role == SourceRole.ORIGINAL_RECORD and by_id[f.source_id].identity_reviewed]
    if authoritative_s and authoritative_c:
        return "CONFLICTING", "HUMAN_REVIEW", None, "reviewed original records conflict"
    if authoritative_c:
        vals = {canonical(f.extracted_value, claim.answer_type) for f in authoritative_c if f.extracted_value}
        correction = next(iter(vals)) if len(vals) == 1 else None
        if correction:
            return "CONTRADICTED", "REVISE", correction, "reviewed original record contradicts the proposed value; verify revision before release"
        return "CONFLICTING", "HUMAN_REVIEW", None, "original records disagree on the correct value"
    if authoritative_s:
        return "ADEQUATE", "ALLOW", None, "direct match in human-reviewed original record"
    if supports and contradicts:
        return "CONFLICTING", "QUALIFY", None, "unresolved contradictory secondary evidence"
    if supports:
        return "INSUFFICIENT", "QUALIFY", None, "secondary or unreviewed support alone does not establish the fact"
    if not claim.evidence_pattern:
        return "NOT_CHECKABLE", "HUMAN_REVIEW", None, "no supported deterministic verifier for this claim type"
    return "INSUFFICIENT", "QUALIFY", None, "no adequate passage supports the claim"


def verify_claim(claim: Claim, sources: list[SourceSnapshot], *,
                 retriever: ArchiveRetriever | None = None,
                 config: VerificationConfig | None = None) -> VerificationReport:
    config = config or VerificationConfig()
    if len({s.source_id for s in sources}) != len(sources):
        raise ValueError("one snapshot per source_id per verification request")
    missing_cites = set(claim.cited_source_ids) - {s.source_id for s in sources}
    if missing_cites and not retriever:
        raise ValueError(f"cited sources not supplied: {sorted(missing_cites)}")
    for source in sources:
        read_snapshot(source)  # fail on corruption, never silently accept modified bytes
    available = list(sources)
    log, fetched = [], []
    for step in range(config.max_extra_fetches + 1):
        findings = find_support(claim, available)
        status, action, correction, reason = _assessment(claim, available, findings, config.mode)
        if status in ("ADEQUATE", "CONTRADICTED", "CONFLICTING", "NOT_CHECKABLE"):
            break
        if retriever is None or step == config.max_extra_fetches:
            break
        new_source = retriever.choose(claim, available, config.mode)
        if not new_source:
            log.append("archive pool exhausted")
            break
        read_snapshot(new_source)
        available.append(new_source)
        fetched.append(new_source.source_id)
        log.append(f"fetch {step + 1}: {new_source.source_id}; strategy={config.mode}")
    relations, pairwise, independence = (inspect_lineage(claim, available)
        if config.mode == "lineage" else ([], [], "UNKNOWN"))
    # Citation check: cited support must exist, even if an uncited record supports the fact.
    if status == "ADEQUATE" and claim.cited_source_ids:
        cited_ok = any(f.source_id in claim.cited_source_ids and f.relation == "SUPPORTS" for f in findings)
        if not cited_ok:
            status, action, correction, reason = "INSUFFICIENT", "QUALIFY", None, "specified citations do not support the claim; uncited evidence cannot validate attribution"
    return VerificationReport(request_id=uuid4().hex, claim=claim, evidence_status=status,
        action=action, findings=findings, relationships=relations,
        pairwise_lineage=pairwise, independence=independence,
        inspected_snapshot_ids=[s.snapshot_id for s in available], retrieved_source_ids=fetched,
        retrieval_log=log, proposed_correction=correction, reason=reason,
        mode=config.mode, policy_version=config.policy_version)


def verify_revision(claim: Claim, new_value: str, sources: list[SourceSnapshot], *,
                    config: VerificationConfig | None = None) -> VerificationReport:
    updated = claim.model_copy(update={"expected_value": new_value,
        "text": f"{claim.subject}: {claim.predicate} = {new_value}", "cited_source_ids": []})
    return verify_claim(updated, sources, config=config)


def verify_answer(question: str, draft_answer: str, atomic_claims: list[Claim],
                  sources: list[SourceSnapshot], *, retriever=None, config=None) -> dict:
    # Explicit atomic claims are required until the claim extractor is independently validated.
    if not question.strip() or not draft_answer.strip() or not atomic_claims:
        raise ValueError("question, draft answer, and explicit atomic claims required")
    reports = [verify_claim(c, sources, retriever=retriever, config=config) for c in atomic_claims]
    overall = ("ALLOW" if all(r.action == "ALLOW" for r in reports)
        else "HUMAN_REVIEW" if any(r.action == "HUMAN_REVIEW" for r in reports)
        else "REVISE" if any(r.action == "REVISE" for r in reports) else "QUALIFY")
    return {"question": question, "draft_answer": draft_answer, "answer_action": overall,
            "reports": [r.model_dump(mode="json") for r in reports],
            "warning": "Host agent must enforce this gate; draft text is not automatically released."}
