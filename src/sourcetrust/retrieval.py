"""Frozen-archive retriever: all modes see only the permitted pool, never hidden answers."""
from __future__ import annotations
from collections.abc import Sequence
from .models import Claim, SourceSnapshot, SourceRole


class ArchiveRetriever:
    def __init__(self, pool: Sequence[SourceSnapshot]):
        self.pool = list(pool)
        ids = [s.source_id for s in self.pool]
        if len(ids) != len(set(ids)):
            raise ValueError("archive retriever expects one selected snapshot per source_id")

    def choose(self, claim: Claim, available: list[SourceSnapshot], mode: str) -> SourceSnapshot | None:
        used = {s.source_id for s in available}
        unseen = [s for s in self.pool if s.source_id not in used]
        if not unseen:
            return None
        # Standard uses an ordinary topic-match ranking. Full lineage can prioritize
        # curated original records and avoid known secondary re-publications.
        def lexical(s: SourceSnapshot) -> int:
            title = (s.page_title or "") + " " + (s.subject or "")
            return int(claim.subject.casefold() in title.casefold())
        if mode in ("lineage", "lineage_ablation"):
            occupied_origins = {origin for s in available if s.attribution_reviewed
                for origin in s.claim_origin_ids.get(claim.predicate, [])}
            def score(s: SourceSnapshot):
                origin_penalty = int(mode == "lineage" and s.attribution_reviewed and
                    bool(set(s.claim_origin_ids.get(claim.predicate, [])) & occupied_origins))
                original = int(s.role == SourceRole.ORIGINAL_RECORD and s.identity_reviewed)
                return (original, -origin_penalty, lexical(s))
        else:
            def score(s: SourceSnapshot):
                return (lexical(s),)
        # Stable pool order when ranks tie; no access to private ground truth or attack labels.
        return sorted(unseen, key=score, reverse=True)[0]
