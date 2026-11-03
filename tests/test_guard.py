import hashlib
from pathlib import Path
import pytest
from sourcetrust.models import Claim, SourceRole, AnswerType, VerificationConfig
from sourcetrust.storage import store_snapshot, read_snapshot
from sourcetrust.passages import extract_passages, verify_passage
from sourcetrust.guard import verify_claim, verify_revision, verify_answer
from sourcetrust.retrieval import ArchiveRetriever
from sourcetrust.lineage import inspect_lineage
from sourcetrust.verifier import canonical


@pytest.fixture
def sample(tmp_path):
    def put(sid, date, role=SourceRole.SECONDARY_REPORT, reviewed=False, upstream=None):
        return store_snapshot(tmp_path, sid, f"https://example.invalid/{sid}",
            f"<html><title>AgentDojo {sid}</title><body><h1>AgentDojo</h1><p>Submitted on {date}.</p></body></html>".encode(),
            role=role, identity_reviewed=reviewed, subject="AgentDojo", subject_reviewed=True,
            attributed_to=upstream or [], attribution_reviewed=bool(upstream),
            claim_origin_ids={"first submission": upstream} if upstream else {})
    a = put("a", "19 Jun 2025", upstream=["rumor"])
    b = put("b", "19 Jun 2025", upstream=["rumor"])
    original = put("original", "19 Jun 2024", role=SourceRole.ORIGINAL_RECORD, reviewed=True)
    return tmp_path, a, b, original


@pytest.fixture
def claim():
    return Claim(claim_id="c1", text="AgentDojo was submitted in 2025", subject="AgentDojo",
        predicate="first submission", expected_value="2025-06-19", answer_type=AnswerType.DATE,
        evidence_pattern=r"Submitted on\s+(?P<value>\d{1,2}\s+[A-Za-z]+\s+\d{4})")


def test_immutable_and_hash(sample):
    root, a, *_ = sample
    duplicate = store_snapshot(root, "a", a.final_url, Path(a.raw_path).read_bytes())
    assert a.snapshot_id != duplicate.snapshot_id
    assert read_snapshot(a)
    Path(a.raw_path).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA256"):
        read_snapshot(a)


def test_offset_and_tamper(sample):
    _, a, *_ = sample
    ps = extract_passages(a)
    assert ps and all(verify_passage(p, a) for p in ps)
    changed = ps[0].model_copy(update={"text": "fake"})
    assert not verify_passage(changed, a)


def test_structured_comparison(sample, claim):
    _, a, b, original = sample
    r = verify_claim(claim, [original])
    assert r.evidence_status == "CONTRADICTED"
    assert r.proposed_correction == "2024-06-19"
    revised = verify_revision(claim, r.proposed_correction, [original])
    assert revised.action == "ALLOW"
    assert verify_claim(claim, [a, b]).evidence_status == "INSUFFICIENT"


def test_lineage_not_invent_independence(sample, claim):
    _, a, b, orig = sample
    edges, pairs, status = inspect_lineage(claim, [a,b])
    assert status == "KNOWN_DEPENDENT" and edges and edges[0].review_status == "REVIEWED"
    assert pairs[0].status == "KNOWN_DEPENDENT"
    assert inspect_lineage(claim, [a, orig])[2] == "UNKNOWN"
    edges, pairs, status = inspect_lineage(claim, [a, b, orig])
    assert status == "UNKNOWN" and [p.status for p in pairs].count("UNKNOWN") == 2


def test_budgeted_retrieval(sample, claim):
    root, a, b, original = sample
    irrelevant = store_snapshot(root, "decoy", "https://example.invalid/decoy",
        b"<html><title>AgentDojo introduction</title><body>AgentDojo tests agents.</body></html>",
        role=SourceRole.SECONDARY_REPORT, subject="AgentDojo")
    pool = ArchiveRetriever([irrelevant, original])
    standard = verify_claim(claim, [a,b], retriever=pool, config=VerificationConfig(mode="standard", max_extra_fetches=1))
    full = verify_claim(claim, [a,b], retriever=pool, config=VerificationConfig(mode="lineage", max_extra_fetches=1))
    assert standard.retrieved_source_ids == ["decoy"]
    assert standard.action == "QUALIFY"
    assert full.retrieved_source_ids == ["original"]
    assert full.action == "REVISE"
    assert len(full.retrieved_source_ids) <= 1


def test_citation_specificity(sample, claim):
    _, a, _, original = sample
    cited = claim.model_copy(update={"expected_value": "2024-06-19", "cited_source_ids": ["a"]})
    result = verify_claim(cited, [a, original])
    assert result.action == "QUALIFY", result
    with pytest.raises(ValueError, match="cited"):
        verify_claim(cited, [original])


def test_no_verified_original_no_allow(sample, claim):
    _, a, b, _ = sample
    assert verify_claim(claim, [a,b]).action == "QUALIFY"


def test_claim_not_checkable(sample, claim):
    _, a, *_ = sample
    plain = claim.model_copy(update={"evidence_pattern": None})
    r = verify_claim(plain, [a])
    assert r.evidence_status == "NOT_CHECKABLE"


def test_answer_gate_and_validation(sample, claim):
    _, a, *_ = sample
    result = verify_answer("when?", claim.text, [claim], [a])
    assert result["answer_action"] == "QUALIFY"
    with pytest.raises(ValueError):
        verify_answer("", "draft", [claim], [a])


def test_date_formats_and_fake_regex(sample, claim):
    assert canonical("June 19, 2024", AnswerType.DATE) == "2024-06-19"
    _, a, *_ = sample
    malformed = claim.model_copy(update={"evidence_pattern": r"Submitted on \d+"})
    with pytest.raises(ValueError, match="named capture"):
        verify_claim(malformed, [a])


def test_temporal_scope_not_silently_ignored(sample, claim):
    _, _, _, original = sample
    scoped = claim.model_copy(update={"expected_value": "2024-06-19", "as_of_date": "2025-01-01"})
    report = verify_claim(scoped, [original])
    assert report.evidence_status == "NOT_CHECKABLE"
    assert report.action == "HUMAN_REVIEW"
