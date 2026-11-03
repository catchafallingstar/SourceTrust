# SourceTrust v1 — research prototype (clean-room start)

**Status: working foundational implementation, not a completed December research release.**

SourceTrust comprises (A) a reusable Python **Guard** for checking bounded, structured factual claims against traceable passages and (B) a **Benchmark** runner for paired frozen-evidence experiments. Its research hypothesis is whether **claim-specific, partly observable source lineage** makes verification and retrieval better than comparably budgeted alternatives. This is not a truth detector or a proven AI-security defense.

This project was built anew; it does **not** require the previous Ubuntu SourceTrust directory, its seed cases, or its virtual environment.

## Ubuntu / WSL fresh install

Prerequisites: Python 3.11+ (3.11/3.12 recommended), `python3-venv`, internet access for pip, and optional Ollama for LLM generation. Unzip the distribution into a new directory, then:

```bash
cd ~/PhdF27fighting/SourceTrust-v1    # adjust if extracted elsewhere
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
pytest -q
python scripts/seed_demo.py --out data/demo_runtime
python examples/verify_claim.py
python examples/verify_software_claim.py
```

`seed_demo.py` creates **fabricated HTML testing pages** with a known bad date. Those are not real collected web evidence and may **not** support empirical accuracy, attack success rate, or defense effectiveness claims.

Expected *demo logic* (not statistical results): standard retrieval with one extra document checks a decoy, while lineage-aware and lineage-ablated retrieval both find a curator-labeled original and can propose a correction. Because the strong ablation does just as well here, this example **does not establish a lineage benefit**.

### Real-source collection and verification

Collect a fresh, immutable AgentDojo arXiv capture:

```bash
sourcetrust collect \
  --url https://arxiv.org/abs/2406.13352 \
  --allow-host arxiv.org \
  --source-id agentdojo_arxiv \
  --subject AgentDojo \
  --root data/real

sourcetrust verify \
  --claim examples/real_agentdojo_claim.json \
  --root data/real
```

The collector **never marks a publisher as reviewed automatically**. Before a primary record can count as adequate, inspect the actual saved text and source URL, verify the publisher identity out-of-band, record who conducted the review and on what basis, and only then change its snapshot JSON metadata in `data/real/snapshots/`: `role` to `ORIGINAL_RECORD`, `subject_reviewed` to `true`, and `identity_reviewed` to `true`. Do not do this to an unverified page or on the basis of its own claims. Run `sourcetrust verify` again. Without review, `QUALIFY` is expected.

The collector creates fresh UUID-named `.raw`, `.txt`, and `.json` files for each capture. It checks raw/text SHA-256 when reading. Capture time is **not** page publication date; hashes establish **stored byte integrity**, not factual accuracy. The collector uses HTTPS, explicit host allowlists, redirect limits, public-address checks and byte limits, but is **not production-hardened** against all DNS-rebinding and hostile networking conditions. Do not expose it as an arbitrary URL fetch API.

## Ollama: real agent draft benchmark (only after sources are reviewed)

Install Ollama on the machine running Ubuntu/WSL, verify its local API is accessible, then obtain the model:

```bash
ollama pull qwen3:14b
ollama list
curl -s http://127.0.0.1:11434/api/tags
```

If Ollama already serves port `11434`, **do not start a second `ollama serve`**. If it runs on Windows while Python runs in WSL, confirm loopback connectivity before running; the adapter currently accepts local loopback endpoints only. Model download is required only for actual LLM benchmarks, **not** for unit tests and deterministic demos.

The public task format is `ResearchTask` JSONL: `task_id`, `question`, `domain`, `subject`, `predicate`, `answer_type`, `evidence_pattern`, `initial_source_ids`, `retrieval_pool_ids`, `scenario_id`, `snapshot_selection`. **No reference or attacker target is allowed in the public task.** Use only real, human-reviewed cases for meaningful experiments; `data/demo_runtime/public_tasks.jsonl` is a fake smoke-test task.

```bash
sourcetrust benchmark \
  --tasks data/demo_runtime/public_tasks.jsonl \
  --root data/demo_runtime \
  --model qwen3:14b \
  --budget 2 \
  --out results/demo_trials.jsonl
```

This invokes the local Qwen model once per task/scenario, **reuses the same initial model draft across defenses**, and compares:

- `no_guard`: the model's raw candidate answer.
- `standard`: deterministic verifier with topical archive retrieval.
- `lineage_ablation`: verifier with reviewed original-record priority, without claim-lineage diversification.
- `lineage`: the same priority, plus reviewed claim-specific source-origin diversification.

`--budget` is the maximum additional document retrievals per defended trial. All defended conditions use the **same** cap. This is a bounded replay harness, **not** a faithful replication of FIRE, ProvenanceGuard, Pandey et al., or any commercial research agent.

After you independently review the reference answers, use a **separate evaluator step**. Demo references are only mock test fixtures:

```bash
sourcetrust evaluate \
  --trials results/demo_trials.jsonl \
  --references data/demo_runtime/PRIVATE_DEMO_REFERENCE_NOT_FOR_AGENT.jsonl \
  --out results/demo_scores.jsonl
```

The evaluator can also receive `--attacks PRIVATE_ATTACKS.jsonl` to compute whether the attack target was adopted and whether a modified snapshot was actually shown to the model. It refuses to score unreviewed references and unreviewed attack metadata. The runner never loads these private files. **Do not report rates calculated on the one-task mock demo as research results.**

## Source code guide

| File | Responsibility |
| --- | --- |
| `models.py` | Pydantic records: immutable source capture identity, offset-based passages, structured claims, relationships, public tasks, private references and reports |
| `collector.py`, `storage.py` | Restricted public collection, HTML→text normalization, versioned snapshots, SHA-256 integrity |
| `passages.py` | Reversible character-offset passages and exact text-span validation |
| `verifier.py` | Claim-specific regex field extraction; exact date/number/identifier comparison; explicit support/contradiction with evidence spans |
| `lineage.py` | Claim-specific reviewed common-origin links; observed versus suspected; **unknown is not independent** |
| `retrieval.py` | Frozen archive lookup with an equal document budget and alternative ranking policies |
| `guard.py` | Evidence sufficiency, citation check, qualification/correction, bounded retrieval, structured report and revision recheck |
| `attacks.py` | Creates **local-only** changed secondary snapshots; retains original bytes and change manifest |
| `ollama.py` | One Qwen draft from a frozen source packet; JSON response with source IDs |
| `benchmark.py` | Clean/modified scenario selection, common draft replay, trial logs, private evaluator |
| `cli.py` | `collect`, `verify`, `benchmark`, `evaluate` commands |

Public API:

```python
from sourcetrust import verify_claim, verify_answer, verify_revision
# verify_claim(claim, snapshots, retriever=..., config=...)
# verify_answer(question, draft, explicit_atomic_claims, snapshots, ...)
# verify_revision(claim, corrected_value, all_inspected_snapshots)
```

**Important limitation:** `verify_answer` currently requires caller-provided **atomic claims**. It cannot yet extract arbitrary natural-language propositions or validate all causal, negative, software-version, or free-text claims. Unhandled types do not silently become certified. `as_of_date` requests are marked `NOT_CHECKABLE` until temporal checking exists.

### Invariants to preserve when extending

1. An LLM or the web cannot mark its own sources `identity_reviewed`; review metadata must be curated separately.
2. `SUPPORTS` is only passage entailment/field agreement, not a guarantee of world truth.
3. `claim_origin_ids` must be reviewer-backed and **specific to the predicate**; homepage links and similar text do not establish ancestry.
4. Two distinct domains or URLs never establish independent evidence by themselves.
5. Unknown lineage must remain UNKNOWN; do not invent confidence or independent-witness counts.
6. The runner never reads reference answers or attack target values.
7. Keep a separate paired `clean` / `attacked` run and record whether changed source bytes actually reached the initial agent prompt.
8. Compare `lineage` against `lineage_ablation` with matched budgets before claiming scientific improvement.
9. A `REVISE` is only a proposed correction until the revised claim is checked again.
10. Local demo fixtures cannot be included in empirical metrics.

## What's still missing before the December research artifact

This first tested version is **not** the complete 13-stage pipeline. It lacks automatic multi-claim decomposition, general semantic/NLI claim verification, extraction of claim-specific citation links from real HTML, genuine independence establishment, a full temporal/version checker, uncertainty-conditioned information-gain retrieval, defensible adequacy policies beyond narrow records, human-review user interface, complete experiment metrics/intervals, and an independently annotated 12–15-task real-source benchmark. These are intentional, recorded limits; see `docs/PIPELINE_AUDIT.md` and `docs/DATA_COLLECTION.md`.
