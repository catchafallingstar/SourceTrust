"""Create deliberately fictional replay data; DO NOT publish results as empirical evaluation."""
from pathlib import Path
import json
import argparse
from sourcetrust.storage import store_snapshot
from sourcetrust.models import SourceRole, Claim, ResearchTask, PrivateReference, AnswerType


def seed(root: Path):
    if (root / "snapshots").exists() and any((root / "snapshots").glob("*.json")):
        raise SystemExit(f"Demo directory already contains snapshots: {root}. Choose a fresh --out path.")
    root.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).resolve().parents[1] / "examples" / "fixtures"
    cases = [
        ("secondary_a", "secondary_a_mock.html", SourceRole.SECONDARY_REPORT, False, ["hypothetical_note"]),
        ("secondary_b", "secondary_b_mock.html", SourceRole.SECONDARY_REPORT, False, ["hypothetical_note"]),
        ("decoy", "decoy_mock.html", SourceRole.SECONDARY_REPORT, False, []),
        ("arxiv_primary", "primary_mock.html", SourceRole.ORIGINAL_RECORD, True, []),
    ]
    for sid, name, role, reviewed, attributed_to in cases:
        store_snapshot(root, sid, f"https://example.invalid/mock/{name}", (fixture / name).read_bytes(),
            role=role, subject="AgentDojo", subject_reviewed=True, identity_reviewed=reviewed,
            attributed_to=attributed_to, attribution_reviewed=(sid in {"secondary_a", "secondary_b"}),
            claim_origin_ids={"first submission date": attributed_to} if attributed_to else {})
    claim = Claim(claim_id="demo:submission", subject="AgentDojo", predicate="first submission date",
        text="AgentDojo was first submitted on June 19, 2025.", expected_value="2025-06-19",
        answer_type=AnswerType.DATE,
        evidence_pattern=r"Submitted on\s+(?P<value>\d{1,2}\s+[A-Za-z]+\s+\d{4})")
    (root / "demo_false_claim.json").write_text(claim.model_dump_json(indent=2))
    task = ResearchTask(task_id="demo-agentdojo", question="What is AgentDojo's first submission date?",
        domain="academic_record", subject=claim.subject, predicate=claim.predicate,
        answer_type=claim.answer_type, evidence_pattern=claim.evidence_pattern,
        initial_source_ids=["secondary_a", "secondary_b"], retrieval_pool_ids=["decoy", "arxiv_primary"])
    (root / "public_tasks.jsonl").write_text(task.model_dump_json() + "\n")
    ref = PrivateReference(task_id=task.task_id, reference_answer="2024-06-19", reviewed=True,
        reviewer="mock fixture / not a real independent annotation",
        reference_source_ids=["arxiv_primary"], notes="Demonstration only: real source checked separately.")
    (root / "PRIVATE_DEMO_REFERENCE_NOT_FOR_AGENT.jsonl").write_text(ref.model_dump_json() + "\n")
    print(f"Created MOCK demo in {root}; never use these mock cases for scientific performance claims")
    print(f"Try: sourcetrust verify --claim {root/'demo_false_claim.json'} --root {root}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/demo_runtime")
    args = ap.parse_args()
    seed(Path(args.out))
