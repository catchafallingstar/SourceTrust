"""Strict public contracts. Reference answers must never be placed in these records."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class AnswerType(str, Enum):
    DATE = "DATE"
    NUMBER = "NUMBER"
    IDENTIFIER = "IDENTIFIER"
    TEXT = "TEXT"


class SourceRole(str, Enum):
    ORIGINAL_RECORD = "ORIGINAL_RECORD"
    FIRSTHAND_OBSERVATION = "FIRSTHAND_OBSERVATION"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    AGGREGATOR = "AGGREGATOR"
    UNKNOWN = "UNKNOWN"


class SourceSnapshot(BaseModel):
    source_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    requested_url: str
    final_url: str
    retrieved_at_utc: datetime
    http_status: int
    content_type: str
    raw_path: str
    raw_sha256: str
    text_path: str
    text_sha256: str
    page_title: str | None = None
    subject: str | None = None
    # These are curated labels, not conclusions from the webpage's self-description.
    role: SourceRole = SourceRole.UNKNOWN
    identity_reviewed: bool = False
    subject_reviewed: bool = False
    attributed_to: list[str] = Field(default_factory=list)
    attribution_reviewed: bool = False
    # Claim-specific reviewed origins; raw document hyperlinks do not count as evidence ancestry.
    claim_origin_ids: dict[str, list[str]] = Field(default_factory=dict)


class EvidencePassage(BaseModel):
    passage_id: str
    snapshot_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str

    @model_validator(mode="after")
    def check_length(self):
        if self.end_offset - self.start_offset != len(self.text):
            raise ValueError("passage offsets must match passage text length")
        return self


class Claim(BaseModel):
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    expected_value: str = Field(min_length=1)
    answer_type: AnswerType
    # Trusted application-owned regex with exactly one named group '(?P<value>...)'.
    # It locates the field, not arbitrary dates in an irrelevant paragraph.
    evidence_pattern: str | None = None
    cited_source_ids: list[str] = Field(default_factory=list)
    as_of_date: str | None = None


class Relationship(BaseModel):
    claim_id: str
    from_source_id: str
    to_source_id: str
    relationship_type: Literal["EXPLICIT_CITATION", "SHARED_UPSTREAM", "NEAR_DUPLICATE", "POSSIBLE_DEPENDENCE"]
    status: Literal["OBSERVED", "SUSPECTED"]
    review_status: Literal["AUTOMATIC", "REVIEWED"]
    evidence_passage_ids: list[str] = Field(default_factory=list)
    rationale: str


class PairwiseLineage(BaseModel):
    left_source_id: str
    right_source_id: str
    status: Literal["KNOWN_DEPENDENT", "POSSIBLY_DEPENDENT", "UNKNOWN", "INDEPENDENCE_ESTABLISHED"]
    rationale: str


class SupportFinding(BaseModel):
    source_id: str
    snapshot_id: str
    passage_id: str
    relation: Literal["SUPPORTS", "CONTRADICTS", "NOT_ADDRESSED", "UNCERTAIN"]
    extracted_value: str | None = None
    quoted_text: str
    rationale: str


class VerificationConfig(BaseModel):
    max_extra_fetches: int = Field(default=2, ge=0, le=20)
    mode: Literal["standard", "lineage", "lineage_ablation"] = "lineage"
    policy_version: str = "bounded-factual-v1"


class VerificationReport(BaseModel):
    request_id: str
    claim: Claim
    evidence_status: Literal["ADEQUATE", "CONTRADICTED", "CONFLICTING", "INSUFFICIENT", "NOT_CHECKABLE", "ERROR"]
    action: Literal["ALLOW", "REVISE", "QUALIFY", "ABSTAIN", "HUMAN_REVIEW", "ERROR"]
    findings: list[SupportFinding]
    relationships: list[Relationship]
    pairwise_lineage: list[PairwiseLineage] = Field(default_factory=list)
    independence: Literal["KNOWN_DEPENDENT", "POSSIBLY_DEPENDENT", "UNKNOWN", "INDEPENDENCE_ESTABLISHED"]
    inspected_snapshot_ids: list[str]
    retrieved_source_ids: list[str]
    retrieval_log: list[str]
    proposed_correction: str | None = None
    reason: str
    policy_version: str
    mode: str
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResearchTask(BaseModel):
    """Agent-visible task. No candidate answer, reference answer, or attack target."""
    task_id: str
    question: str
    domain: str
    subject: str
    predicate: str
    answer_type: AnswerType
    evidence_pattern: str
    initial_source_ids: list[str]
    retrieval_pool_ids: list[str]
    scenario_id: str = "clean"
    # Exact capture for each visible source; permits clean/poisoned paired replays.
    snapshot_selection: dict[str, str] = Field(default_factory=dict)


class PrivateAttack(BaseModel):
    """Evaluator-only. Never import or pass to the agent or Guard."""
    task_id: str
    scenario_id: str
    condition: str
    modified_snapshot_ids: list[str]
    target_wrong_answer: str
    original_snapshot_ids: list[str] = Field(default_factory=list)
    changed_spans: list[str] = Field(default_factory=list)
    control_surface: str = "local archived secondary evidence"
    validity_reviewed: bool = False
    reviewer: str = ""


class PrivateReference(BaseModel):
    task_id: str
    reference_answer: str
    reviewed: bool = False
    reviewer: str = ""
    reference_source_ids: list[str] = Field(default_factory=list)
    notes: str = ""
