from __future__ import annotations
import argparse
import json
from pathlib import Path
from .collector import collect_public
from .models import Claim, SourceRole, VerificationConfig
from .storage import load_snapshots
from .guard import verify_claim
from .benchmark import run_tasks, evaluate


def main():
    ap = argparse.ArgumentParser(prog="sourcetrust", description="SourceTrust v1 research prototype")
    sp = ap.add_subparsers(dest="command", required=True)
    c = sp.add_parser("collect", help="Save an immutable public-HTTPS snapshot")
    c.add_argument("--url", required=True)
    c.add_argument("--source-id", required=True)
    c.add_argument("--root", default="data")
    c.add_argument("--allow-host", action="append", required=True)
    c.add_argument("--subject")
    v = sp.add_parser("verify", help="Verify a structured factual claim against snapshots")
    v.add_argument("--claim", required=True, help="path to Claim JSON")
    v.add_argument("--root", default="data")
    v.add_argument("--mode", choices=["standard", "lineage", "lineage_ablation"], default="lineage")
    b = sp.add_parser("benchmark", help="Generate fixed Qwen draft, compare defense modes")
    b.add_argument("--tasks", required=True)
    b.add_argument("--root", default="data")
    b.add_argument("--out", default="results/trials.jsonl")
    b.add_argument("--model", default="qwen3:14b")
    b.add_argument("--budget", type=int, default=2)
    e = sp.add_parser("evaluate", help="Private evaluation only; requires reviewer references")
    e.add_argument("--trials", required=True)
    e.add_argument("--references", required=True)
    e.add_argument("--out", default="results/scores.jsonl")
    e.add_argument("--attacks", help="evaluator-only attack metadata JSONL")
    args = ap.parse_args()
    if args.command == "collect":
        x = collect_public(args.root, args.source_id, args.url,
            allowed_hosts=set(args.allow_host), subject=args.subject)
        print(x.model_dump_json(indent=2))
    if args.command == "verify":
        claim = Claim.model_validate_json(Path(args.claim).read_text())
        result = verify_claim(claim, load_snapshots(args.root), config=VerificationConfig(mode=args.mode, max_extra_fetches=0))
        print(result.model_dump_json(indent=2))
    if args.command == "benchmark":
        path, n = run_tasks(args.tasks, args.root, args.out, model=args.model, budget=args.budget)
        print(f"{n} trial records written to {path}. No evaluation references read; no metrics claimed.")
    if args.command == "evaluate":
        scores = evaluate(args.trials, args.references, args.attacks)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            for row in scores: f.write(json.dumps(row) + "\n")
        print(f"{len(scores)} independently scored rows written to {args.out}")
        for mode in sorted({r["mode"] for r in scores}):
            sub = [r for r in scores if r["mode"] == mode]
            accuracy = sum(r["correct"] for r in sub) / len(sub)
            coverage = sum(r["covered"] for r in sub) / len(sub)
            print(f"{mode}: correct/task={accuracy:.3f}; coverage={coverage:.3f}; tasks={len(sub)}")

if __name__ == "__main__": main()
