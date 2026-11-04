"""Self-reported attention; no elapsed-time inference and no fabricated approvals."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
import uuid

from .util import ROOT, now, read_json, review_version, write_json

PREPARATION = ("elicitation", "validation", "corrections", "approval")
CATEGORIES = PREPARATION + ("source_construction", "tooling", "maintenance")


def records(root: Path = ROOT):
    path = root / "expert/time-log.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def log(*, activity: str, category: str, reviewer: str, minutes: float | None,
        method: str, notes: str = "", replaces: str | None = None,
        session: str = "review-1", round_number: int = 1, root: Path = ROOT,
        artifact_version: str | None = None):
    if category not in CATEGORIES or method not in ("timed", "estimated", "missing"):
        raise ValueError("Invalid category or measurement method")
    if not activity.strip() or not reviewer.strip() or not session.strip() or round_number < 1:
        raise ValueError("Activity, reviewer, session, and positive revision round are required")
    if method == "missing" and minutes is not None:
        raise ValueError("Missing reports cannot have a duration")
    if method != "missing" and (minutes is None or not math.isfinite(minutes) or minutes < 0):
        raise ValueError("Report finite nonnegative active minutes, or mark the report missing")
    if artifact_version is not None and not re.fullmatch(r"[a-f0-9]{64}", artifact_version):
        raise ValueError("Artifact version must be the 64-character hash printed by ./reserve check")
    old = records(root)
    superseded = {r["replaces"] for r in old if r.get("replaces")}
    if replaces and (replaces not in {r["id"] for r in old} or replaces in superseded):
        raise ValueError("A correction must reference an existing, not already superseded report")
    row = {"id": uuid.uuid4().hex[:12], "recorded_at": now(), "reviewer": reviewer,
           "activity": activity, "category": category, "active_minutes": minutes,
           "method": method, "basis": "self_reported", "notes": notes,
           "replaces": replaces, "review_session": session, "revision_round": round_number,
           "artifact_version": artifact_version or review_version(root)}
    path = root / "expert/time-log.jsonl"
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    return row


def summary(root: Path = ROOT):
    rows = records(root)
    superseded = {r["replaces"] for r in rows if r.get("replaces")}
    active = [r for r in rows if r["id"] not in superseded]
    included = [r for r in active if r["category"] in PREPARATION]
    reported = [r for r in included if r["active_minutes"] is not None]
    status = read_json(root / "reference/approval.json")
    approved = status["status"] == "approved" and status["review_version"] == review_version(root)
    return {
        "unit": "self-reported active person-minutes per practice pair",
        "reported_preparation_minutes": sum(r["active_minutes"] for r in reported) if reported else None,
        "missing_reports": len(included) - len(reported),
        "measurement_status": "no reports yet" if not included else "reported work only; check approval and missing entries",
        "human_approved_current_version": approved,
        "by_category": {c: sum(r["active_minutes"] or 0 for r in active if r["category"] == c)
                        if any(r["category"] == c and r["active_minutes"] is not None for r in active) else None
                        for c in CATEGORIES},
        "review_sessions": len({(r["reviewer"], r["review_session"]) for r in included}),
        "revision_rounds": sorted({r["revision_round"] for r in included}),
        "estimated_reports": sum(r["method"] == "estimated" for r in included),
        "timed_reports": sum(r["method"] == "timed" for r in included),
        "note": "No reports does not mean zero effort. Agent runtime is not human attention. This does not measure net savings.",
    }


def approve(reviewer: str, minutes: float, method: str, root: Path = ROOT):
    row = log(activity="Final approval of both cases, their diagnoses, and feedback guide",
              category="approval", reviewer=reviewer, minutes=minutes, method=method, root=root)
    status = {"status": "approved", "reviewer": reviewer, "review_version": review_version(root),
              "approved_at": now(), "attention_report_id": row["id"]}
    write_json(root / "reference/approval.json", status)
    return status
