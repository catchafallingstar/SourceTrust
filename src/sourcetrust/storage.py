"""Immutable snapshot creation, reading, and integrity checks."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from bs4 import BeautifulSoup
from .models import SourceSnapshot, SourceRole


def html_to_text(content: bytes) -> tuple[str, str | None]:
    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    for node in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        node.decompose()
    # Preserve block separations for exact passage offsets in normalized text.
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return text, title


def store_snapshot(root: str | Path, source_id: str, url: str, raw: bytes, *,
                   content_type: str = "text/html", status: int = 200,
                   role: SourceRole = SourceRole.UNKNOWN, subject: str | None = None,
                   identity_reviewed: bool = False, subject_reviewed: bool = False,
                   attributed_to: list[str] | None = None, attribution_reviewed: bool = False,
                   claim_origin_ids: dict[str, list[str]] | None = None,
                   final_url: str | None = None) -> SourceSnapshot:
    if not source_id or not raw:
        raise ValueError("source_id and nonempty raw bytes required")
    if content_type.startswith("text/html"):
        text, title = html_to_text(raw)
    elif content_type.startswith("text/plain"):
        text, title = raw.decode("utf-8", errors="replace"), None
    else:
        raise ValueError("only HTML and plain text are supported")
    if not text.strip():
        raise ValueError("no extractable text")
    folder = Path(root) / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    # A new UUID, exclusive creation and atomic metadata publication prevent overwrite.
    snapshot_id = uuid4().hex
    raw_path = folder / f"{snapshot_id}.raw"
    text_path = folder / f"{snapshot_id}.txt"
    for target, payload in ((raw_path, raw), (text_path, text.encode("utf-8"))):
        with target.open("xb") as handle:
            handle.write(payload)
    snapshot = SourceSnapshot(source_id=source_id, snapshot_id=snapshot_id,
        requested_url=url, final_url=final_url or url,
        retrieved_at_utc=datetime.now(timezone.utc), http_status=status,
        content_type=content_type, raw_path=str(raw_path), text_path=str(text_path),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        page_title=title, subject=subject, role=role, identity_reviewed=identity_reviewed,
        subject_reviewed=subject_reviewed, attributed_to=attributed_to or [],
        attribution_reviewed=attribution_reviewed, claim_origin_ids=claim_origin_ids or {})
    (folder / f"{snapshot_id}.json").write_text(snapshot.model_dump_json(indent=2))
    return snapshot


def read_snapshot(snapshot: SourceSnapshot) -> str:
    raw = Path(snapshot.raw_path).read_bytes()
    text = Path(snapshot.text_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != snapshot.raw_sha256:
        raise ValueError("snapshot raw SHA256 mismatch")
    if hashlib.sha256(text).hexdigest() != snapshot.text_sha256:
        raise ValueError("snapshot text SHA256 mismatch")
    return text.decode("utf-8")


def load_snapshots(root: str | Path) -> list[SourceSnapshot]:
    folder = Path(root) / "snapshots"
    return [SourceSnapshot.model_validate_json(p.read_text()) for p in sorted(folder.glob("*.json"))] if folder.exists() else []
