"""Second-domain example using a fictional release note, not factual vulnerability data."""
from pathlib import Path
from tempfile import TemporaryDirectory
from sourcetrust.storage import store_snapshot
from sourcetrust.models import Claim, SourceRole, AnswerType
from sourcetrust.guard import verify_claim

with TemporaryDirectory() as folder:
    snap = store_snapshot(folder, "release", "https://example.invalid/fixture",
        b"<html><title>DemoTool release</title><body><h1>DemoTool</h1><p>Released on 10 Oct 2026.</p></body></html>",
        role=SourceRole.ORIGINAL_RECORD, subject="DemoTool", subject_reviewed=True,
        identity_reviewed=True)
    claim = Claim(claim_id="release", text="DemoTool released 10 Oct 2026", subject="DemoTool",
        predicate="release date", expected_value="2026-10-10", answer_type=AnswerType.DATE,
        evidence_pattern=r"Released on\s+(?P<value>\d{1,2}\s+[A-Za-z]+\s+\d{4})")
    report = verify_claim(claim, [snap])
    print(report.evidence_status, report.action)
