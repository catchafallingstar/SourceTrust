"""Claim-specific source lineage; pairwise unknowns are preserved explicitly."""
from __future__ import annotations
from itertools import combinations
from .models import SourceSnapshot, Relationship, Claim, PairwiseLineage


def inspect_lineage(claim: Claim, sources: list[SourceSnapshot]) -> tuple[list[Relationship], list[PairwiseLineage], str]:
    edges: list[Relationship] = []
    pairwise: list[PairwiseLineage] = []
    for a, b in combinations(sources, 2):
        # DO NOT use general hyperlinks to establish a claim-specific chain.
        origin_a = set(a.claim_origin_ids.get(claim.predicate, []))
        origin_b = set(b.claim_origin_ids.get(claim.predicate, []))
        common = origin_a & origin_b
        a_cites_b = b.source_id in origin_a
        b_cites_a = a.source_id in origin_b
        linked = bool(common or a_cites_b or b_cites_a)
        reviewed = a.attribution_reviewed and b.attribution_reviewed
        if linked and reviewed:
            pair_status = "KNOWN_DEPENDENT"
            typ, edge_status, review = ("SHARED_UPSTREAM" if common else "EXPLICIT_CITATION", "OBSERVED", "REVIEWED")
        elif linked:
            pair_status = "POSSIBLY_DEPENDENT"
            typ, edge_status, review = "POSSIBLE_DEPENDENCE", "SUSPECTED", "AUTOMATIC"
        else:
            pair_status = "UNKNOWN"
        pairwise.append(PairwiseLineage(left_source_id=a.source_id, right_source_id=b.source_id,
            status=pair_status, rationale=("claim-specific reviewed origin" if reviewed and linked
                else "unreviewed possible link" if linked else "no established relationship; not proof of independence")))
        if linked:
            # Preserve directed citations. Shared upstream is symmetric, stored as a pair.
            frm, to = (a.source_id, b.source_id)
            if not common and b_cites_a and not a_cites_b:
                frm, to = b.source_id, a.source_id
            edges.append(Relationship(claim_id=claim.claim_id, from_source_id=frm,
                to_source_id=to, relationship_type=typ, status=edge_status,
                review_status=review, rationale=pairwise[-1].rationale))
    states = [p.status for p in pairwise]
    # A mixture of confirmed dependent and unresolved pairs is UNKNOWN overall.
    if states and all(st == "KNOWN_DEPENDENT" for st in states):
        aggregate = "KNOWN_DEPENDENT"
    elif states and all(st in ("KNOWN_DEPENDENT", "POSSIBLY_DEPENDENT") for st in states):
        aggregate = "POSSIBLY_DEPENDENT"
    else:
        aggregate = "UNKNOWN"
    return edges, pairwise, aggregate
