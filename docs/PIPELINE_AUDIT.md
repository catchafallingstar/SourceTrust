# Review of the uploaded 50-page SourceTrust implementation specification (Oct 25, 2026)

## Decision

The specification's **high-level research direction is sound as a bounded prototype proposal**. The strongest scientific question is whether using *claim-specific, partially observed source dependence* changes retrieval and factual-answer decisions, given the same model and document budget. It must not be presented as novel or effective without comparison to published systems and independent experiments.

## Corrections applied before coding

1. **Prevent answer leakage:** user-visible `ResearchTask` must not contain the correct answer, attack goal or prefilled answer value. Reference files are only read by the separately invoked evaluator.
2. **Distinguish ancestry from similarity/attribution:** ordinary hyperlinks, self-declared origin, similar phrasing and different URLs do not establish independence or dependence. Observed claim-specific common-origin links require reviewer evidence; unknown stays unknown.
3. **Require inspectable passages:** support must reference a substring verified against a SHA-256 checked capture, with offsets. A model-generated quote alone is not evidence.
4. **Separate relevance, support, source authenticity and sufficiency:** matching dates in a secondary page can support a sentence *in the page*, but does not make it adequately established.
5. **Avoid false certainty on temporal scope:** current restricted implementation does not auto-authorize `as_of_date` facts or software release applicability questions.
6. **Make revision contingent on re-verification:** a correction is proposed only after a reviewed original record contradicts the draft; the revised claim must pass before release.
7. **Control experimental budgets:** same initial draft, same frozen candidate pool and retrieval cap for the defended configurations. Distinguish standard relevance baseline from the stronger `lineage_ablation` baseline, which shares original-record priority with the full system.
8. **Preserve controls and denominators:** paired original/modified replay, legitimate repetition and genuine contradiction; `attack_exposed_to_agent` separately recorded. Do not score a missing gold answer as an error.
9. **Threat model:** attacker can modify selected secondary local snapshots; no changing original authoritative archives, evaluation code or private references. No attack publication to the open web.
10. **Separate engineering completion from evidence of effectiveness:** a passed software test is not an observed accuracy gain. A small hand-crafted example is not a research benchmark.

## Stage-by-stage implementation status (October 26 version)

| Blueprint stage | Status | Implemented now / not yet |
| --- | --- | --- |
| 0. Request validation | Partial | Pydantic records, unique source IDs, explicit claims; not a full third-party agent integration contract |
| 1. Collect/preserve | Working limited | HTTPS allowlist and immutable HTML/text snapshots, integrity; public fetch hardening still needed |
| 2. Exact passages | Working limited | Offset-preserving text chunks; no sophisticated table/boilerplate/citation extraction |
| 3. Extract claims | **Not implemented** | API requires explicit atomic claims; benchmark currently uses a single typed answer value |
| 4. Match evidence | Working limited | Developer-specified predicate regex rather than general lexical/semantic ranking |
| 5. Support/contradiction | Working limited | Exact DATE/NUMBER/IDENTIFIER typed field comparisons only; no NLI/free-text truth classification |
| 6. Context/identity | Partial | Manual source role and reviewed identity; no reliable automatic publisher verification |
| 7. Lineage | Partial | Reviewed claim-specific common origins and UNKNOWN; suspected edge scaffolding; no automatic inference of full web provenance |
| 8. Temporal | **Not implemented** | Date **value** normalization is implemented; actual `as_of_date` is fail-closed |
| 9. Adequacy | Working narrow | Reviewed original evidence may suffice; ambiguous secondary reports qualify; no broad scientific sufficiency rules |
| 10. Retrieve more | Working limited | Bounded archive lookup, candidate selection and retrieval logs; no live information-gain model |
| 11. Report | Working limited | Per-claim evidence spans, mode, correction, retrieval log and relationship status |
| 12. Answer gate | Working limited | Allow/qualify/revise/human review; explicit revision recheck; host must enforce decisions |
| Research benchmark | Working framework | Scenario-specific snapshots, shared model draft, 4 conditions, separate evaluator; **not yet real reviewed dataset or publishable experiment** |

## Critical scientific caveat

Original-record retrieval, better semantic support checking, and provenance-aware retrieval are **different interventions**. If full SourceTrust beats a weak topical baseline but **not** the original-record-priority ablation, the results do *not* support a provenance-specific advantage. Likewise, if the benefit is only higher abstention, coverage and conditional accuracy must be reported together.

Do not treat source metadata or the examples' manually curated original-record label as an oracle available in real deployments. The benchmark must review authenticity and ancestry using independently collected evidence, without reading the gold factual answer while labeling source reliability. Evaluate potential annotation leakage.

## Next development milestones

A. Add a conservative general claim extractor and a semantic/NLI support checker. Require exact quoted spans and low-risk fallbacks on disagreement.

B. Parse document links and surrounding attribution statements, then validate claim-specific lineage against human-reviewed relationships. Never infer independence from no detected edge.

C. Implement time/version aware assessments, a source-selection policy that responds to *unknown* as distinct from *known shared origin*, and a stronger standard baseline.

D. Collect and annotate real original and secondary captures across two domains. Freeze all versions, run conditions with seeds/repeats and equal model/search budgets, and analyze paired accuracy, attack-induced error, over-abstention, false lineage, latency and uncertainty intervals.
