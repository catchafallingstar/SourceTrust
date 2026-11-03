"""Run after: python scripts/seed_demo.py --out data/demo_runtime"""
from sourcetrust.models import Claim, VerificationConfig
from sourcetrust.storage import load_snapshots
from sourcetrust.retrieval import ArchiveRetriever
from sourcetrust.guard import verify_claim, verify_revision
from pathlib import Path

root = Path("data/demo_runtime")
claim = Claim.model_validate_json((root / "demo_false_claim.json").read_text())
sources = {s.source_id: s for s in load_snapshots(root)}
initial = [sources["secondary_a"], sources["secondary_b"]]
pool = ArchiveRetriever([sources["decoy"], sources["arxiv_primary"]])
for mode in ("standard", "lineage_ablation", "lineage"):
    result = verify_claim(claim, initial, retriever=pool,
        config=VerificationConfig(mode=mode, max_extra_fetches=1))
    print(f"{mode}: {result.evidence_status}, {result.action}, fetched={result.retrieved_source_ids}, "
          f"lineage={result.independence}, correction={result.proposed_correction}")
    if result.proposed_correction:
        visited = [s for s in sources.values() if s.snapshot_id in result.inspected_snapshot_ids]
        rechecked = verify_revision(claim, result.proposed_correction, visited,
            config=VerificationConfig(max_extra_fetches=0, mode=mode))
        print(f"revision verified: {rechecked.action}")
