"""Lossless evidence passage segmentation; no synthesized quotes."""
from __future__ import annotations
from .models import SourceSnapshot, EvidencePassage
from .storage import read_snapshot


def extract_passages(snapshot: SourceSnapshot, *, max_chars: int = 650) -> list[EvidencePassage]:
    if max_chars < 80:
        raise ValueError("max_chars must be >= 80")
    text = read_snapshot(snapshot)
    result = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split = text.rfind("\n", start + max_chars // 3, end)
            if split > start:
                end = split + 1
        part = text[start:end]
        if part.strip():
            result.append(EvidencePassage(passage_id=f"{snapshot.snapshot_id}:p{len(result)}",
                snapshot_id=snapshot.snapshot_id, start_offset=start, end_offset=end, text=part))
        start = end
    return result


def verify_passage(passage: EvidencePassage, snapshot: SourceSnapshot) -> bool:
    if passage.snapshot_id != snapshot.snapshot_id:
        return False
    content = read_snapshot(snapshot)
    return content[passage.start_offset:passage.end_offset] == passage.text
