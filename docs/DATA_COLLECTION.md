# What data the research needs (and what you do NOT need to download today)

## Today

You do **not** need to clone any benchmark repository to install or test SourceTrust. `pytest` and `seed_demo.py` are self-contained. The optional Qwen3 model is downloaded via `ollama pull qwen3:14b` only when you want to run a model-generated-agent draft.

For the **first real record**, collect `https://arxiv.org/abs/2406.13352` (AgentDojo). A current arXiv record shows its initial submission in June 2024 and a November 2024 revision. Preserve the actual page bytes; do not substitute the deliberately mocked example HTML. Verify and document the date independently before writing a gold record.

Use the command in the project README, inspect `data/real/snapshots/<id>.txt` and `.json`, and create a review log in a file outside the agent's input directory. Only then label original/secondary roles and define a specific evidence regex.

## Benchmark dataset (target: 12–15 reviewed tasks, at least 8 modifiable)

Recommended split: **6–8 academic record tasks** plus **6–7 software/security record tasks**, selecting questions with explicit, verifiable answers and reasonably accessible original records. Do not select only questions already easy for Qwen or only those with a perfect primary record. Include benign legitimate repetition and unresolved provenance controls.

**Academic sources:** arXiv submission/version history, paper DOI pages and publisher records, conference/organization announcements. Start with AgentDojo (`https://arxiv.org/abs/2406.13352`). Other candidates need independent confirmation of exact title, date, DOI and what the question means (first submission != latest revision != publication).

**Software/security sources:** maintainer security advisories, release notes, Python Software Foundation advisories (`https://github.com/psf/advisory-database`) or official CVE list (`https://github.com/CVEProject/cvelistV5`). Choose questions such as 'Which release first documented this fix?' and 'Which CVE identifier is explicitly named by this advisory?'. A CVE description or an OSV aggregation is not automatically an original record for every claim. Version-range and affected-product comparisons need the version checker (not implemented yet).

**Optional external datasets (later, for external validity/baselines):** AVeriTeC (`https://fever.ai/dataset/averitec.html`) for labeled real-world claim verification; HAE-GEO (`https://github.com/ant-research/HAE-GEO`) for a related web-poisoning experiment. They are *not* turnkey datasets with reviewed source ancestry tailored to our hypothesis. Do not copy their labels into the Guard input. Check the licenses and whether text redistribution is permitted before releasing archives.

## Per-task annotation checklist

For each **public** task, save: task ID, domain, precise question, supported answer type and predicate, time scope, initially visible source IDs and separate frozen retrieval-pool IDs. For each source, save exact URL, final URL, capture time, raw bytes/hash, normalized text/hash, source role and the role/identity annotation's *basis*. Annotate exact support/contradiction spans and clear evidence lineage (who cites whom for **that specific claim**). Label suspected and unknown separately from observed common origin.

For the **private evaluator only**, save: reference answer, independently supporting original source and passage, reviewer identity, review date/status, disagreement notes, attack goal, permitted changed spans, modified vs original snapshot IDs, and whether the attack manipulation was considered valid.

A defensible review process requires at least one independent human review for all scored references, a second reviewer for ambiguous cases, and systematic recording of disagreement. The reviewed label should describe **what was verified** (source identity, attribution, factual value); never assume all three are the same.

## Controlled scenarios

For an eligible task, create `clean` and mutated selections of the same secondary source. Preserve all captures as distinct `snapshot_id`s, even when they share `source_id`. The `ResearchTask.snapshot_selection` field fixes which version the agent sees. Build additional shared-false-origin, unknown-origin, legitimate-repetition, and contradiction scenarios after annotating source relationships. The evaluator-only attack manifest specifies the goal; it is not accessible to the model or verifier. Count attack success *only* when the goal matches the actual final answer, and separately mark whether the modified snapshot reached the initial prompt.

## Research artifacts to save before reporting performance

Commit the complete source code, exact frozen task manifest, source metadata/hashes, review methodology, model version/checksum, temperature/seed settings, repeated trial traces, retrieval budgets, and scored outputs. Review redistribution and archive licenses: the repository can publish URLs/hashes and collection scripts without automatically republishing every publisher's full text.

Do not report ASR or other efficacy figures from the mock fixture. The statistical unit is a distinct **task**, not every repeated model generation. Report paired task outcomes with uncertainty bounds where defensible, not just raw percentage points.
