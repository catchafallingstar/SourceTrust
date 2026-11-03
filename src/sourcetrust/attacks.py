"""Make a local mutated snapshot only on an explicitly allowed secondary surface."""
from __future__ import annotations
from pathlib import Path
from .models import SourceRole, SourceSnapshot
from .storage import store_snapshot


def mutate_secondary_html(root: str | Path, original: SourceSnapshot, old: bytes,
                          new: bytes) -> tuple[SourceSnapshot, dict]:
    if original.role not in (SourceRole.SECONDARY_REPORT, SourceRole.AGGREGATOR, SourceRole.UNKNOWN):
        raise ValueError("cannot modify designated original/firsthand records")
    if not old or not new or old == new:
        raise ValueError("meaningful substitution required")
    raw = Path(original.raw_path).read_bytes()
    if raw.count(old) != 1:
        raise ValueError("original exact span must occur once")
    attacked = raw.replace(old, new, 1)
    snap = store_snapshot(root, original.source_id, original.requested_url, attacked,
        content_type=original.content_type, role=original.role, subject=original.subject,
        identity_reviewed=original.identity_reviewed, subject_reviewed=original.subject_reviewed,
        attributed_to=original.attributed_to, attribution_reviewed=original.attribution_reviewed,
        claim_origin_ids=original.claim_origin_ids)
    return snap, {"original_snapshot_id": original.snapshot_id,
        "modified_snapshot_id": snap.snapshot_id, "source_id": snap.source_id,
        "old_span": old.decode("utf-8", errors="replace"),
        "new_span": new.decode("utf-8", errors="replace"),
        "control_surface": "local archived secondary HTML"}
