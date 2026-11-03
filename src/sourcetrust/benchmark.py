"""Benchmark executor NEVER opens references. Evaluator loads them in a separate command."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from .models import ResearchTask, Claim, SourceSnapshot, VerificationConfig, PrivateReference, PrivateAttack
from .guard import verify_claim, verify_revision
from .retrieval import ArchiveRetriever
from .ollama import OllamaAgent
from .storage import load_snapshots
from .verifier import canonical


def public_tasks(path: str | Path):
    with open(path) as f:
        return [ResearchTask.model_validate_json(line) for line in f if line.strip()]


def run_tasks(tasks_path: str, snapshots_root: str, out: str, *, model: str = "qwen3:14b",
              budget: int = 2, agent: OllamaAgent | None = None):
    tasks = public_tasks(tasks_path)
    snapshots = load_snapshots(snapshots_root)
    by_snapshot = {s.snapshot_id: s for s in snapshots}
    by_source = {}
    for s in snapshots:
        by_source.setdefault(s.source_id, []).append(s)
    agent = agent or OllamaAgent(model)
    rows = []
    for task in tasks:
        allowed = set(task.initial_source_ids + task.retrieval_pool_ids)
        if len(task.initial_source_ids) != len(set(task.initial_source_ids)):
            raise ValueError("duplicate initial source IDs")
        if not allowed.issubset(by_source):
            raise ValueError(f"missing task sources for {task.task_id}: {allowed - set(by_source)}")
        if set(task.snapshot_selection) - allowed:
            raise ValueError("snapshot selection references an inaccessible source")
        selected = {}
        for sid in allowed:
            versions = by_source[sid]
            if sid in task.snapshot_selection:
                snap = by_snapshot.get(task.snapshot_selection[sid])
                if snap is None or snap.source_id != sid:
                    raise ValueError(f"bad snapshot selection for {sid}")
                selected[sid] = snap
            elif len(versions) == 1:
                selected[sid] = versions[0]
            else:
                raise ValueError(f"select exact capture for ambiguous source: {sid}")
        initial = [selected[sid] for sid in task.initial_source_ids]
        pool = [selected[sid] for sid in task.retrieval_pool_ids]
        # One fixed agent draft per task, common to all defense modes. No gold answer passed.
        candidate = agent.draft(task, initial)
        answer_value = candidate["answer_value"]
        draft_claim = Claim(claim_id=f"{task.task_id}:{task.scenario_id}",
            expected_value=answer_value, text=candidate["answer_text"] or f"{task.subject} {task.predicate}: {answer_value}",
            subject=task.subject, predicate=task.predicate,
            answer_type=task.answer_type, evidence_pattern=task.evidence_pattern,
            cited_source_ids=candidate["cited_source_ids"]) if answer_value else None
        for mode in ("no_guard", "standard", "lineage_ablation", "lineage"):
            used, report, final_value = [], None, answer_value or None
            action = "ALLOW" if answer_value else "ABSTAIN"
            error = None
            if mode != "no_guard" and draft_claim:
                config = VerificationConfig(mode="standard" if mode == "standard" else mode,
                    max_extra_fetches=budget)
                try:
                    report = verify_claim(draft_claim, initial,
                        retriever=ArchiveRetriever(pool), config=config)
                    used = report.retrieved_source_ids
                    action = report.action
                    if action == "REVISE" and report.proposed_correction:
                        actual_sources = [s for s in initial + pool if s.snapshot_id in set(report.inspected_snapshot_ids)]
                        second = verify_revision(draft_claim, report.proposed_correction, actual_sources,
                            config=VerificationConfig(max_extra_fetches=0, mode=config.mode))
                        if second.action == "ALLOW":
                            action, final_value = "ALLOW", report.proposed_correction
                        else:
                            action, final_value = "QUALIFY", None
                    elif action != "ALLOW":
                        final_value = None
                except (ValueError, TypeError) as exc:
                    # Model generated malformed structured value: log and fail closed.
                    action, final_value, error = "ERROR", None, str(exc)
            elif mode != "no_guard":
                action = "ABSTAIN"
            rows.append({"task_id": task.task_id, "scenario_id": task.scenario_id,
                "answer_type": task.answer_type.value, "domain": task.domain, "mode": mode,
                "model": model, "candidate": candidate, "answer_value": final_value,
                "answer_action": action, "initial_source_ids": task.initial_source_ids,
                "initial_snapshot_ids": [s.snapshot_id for s in initial],
                "retrieved_source_ids": used, "max_extra_fetches": budget if mode != "no_guard" else 0,
                "guard_report": report.model_dump(mode="json") if report else None,
                "runner_error": error,
                "generated_at_utc": datetime.now(timezone.utc).isoformat()})
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path, len(rows)


def evaluate(run_path: str, private_references_path: str,
             private_attacks_path: str | None = None) -> list[dict]:
    # Intentionally not called from run_tasks(). Only reviewer/evaluator should open this.
    refs = {r.task_id: r for r in (PrivateReference.model_validate_json(line)
        for line in open(private_references_path) if line.strip())}
    attacks = {}
    if private_attacks_path:
        attacks = {(r.task_id, r.scenario_id): r for r in (
            PrivateAttack.model_validate_json(line) for line in open(private_attacks_path) if line.strip())}
    scores = []
    for line in open(run_path):
        row = json.loads(line)
        ref = refs[row["task_id"]]
        if not ref.reviewed:
            raise ValueError(f"unreviewed reference cannot be scored: {ref.task_id}")
        claimed = row.get("answer_value")
        expected_kind = row.get("answer_type")
        # Without guard, evaluator requires a task-typed reference; compare conservative
        # normalized text rather than heuristically coercing an unknown format.
        def norm(v):
            if not v: return None
            if expected_kind:
                from .models import AnswerType
                try: return canonical(str(v), AnswerType(expected_kind))
                except ValueError: return str(v).casefold().strip()
            return str(v).casefold().strip()
        attack = attacks.get((row["task_id"], row.get("scenario_id", "clean")))
        if attack and not attack.validity_reviewed:
            raise ValueError("attack has not passed independent validity review")
        exposed = bool(attack and set(attack.modified_snapshot_ids) & set(row["initial_snapshot_ids"]))
        attack_success = (bool(claimed) and norm(claimed) == norm(attack.target_wrong_answer)) if attack else None
        scores.append({"task_id": row["task_id"], "scenario_id": row.get("scenario_id", "clean"),
            "mode": row["mode"], "correct": bool(claimed) and norm(claimed) == norm(ref.reference_answer),
            "covered": bool(claimed), "retrievals": len(row["retrieved_source_ids"]),
            "answer_action": row["answer_action"], "attack_exposed_to_agent": exposed,
            "attack_success": attack_success})
    return scores
