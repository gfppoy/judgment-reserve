"""Self-reported attention; no elapsed-time inference and no fabricated approvals."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
import uuid

from .util import ROOT, now, read_json, review_version, write_json

PREPARATION = ("elicitation", "validation", "corrections", "approval")
# Mixed reports combine case preparation and tooling without a reported split.
# Keep their minutes outside the narrower case-preparation subtotal.
CATEGORIES = PREPARATION + ("source_construction", "tooling", "maintenance", "feedback_review", "mixed")


def records(root: Path = ROOT):
    path = root / "expert/time-log.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def log(*, activity: str, category: str, reviewer: str, minutes: float | None,
        method: str, notes: str = "", replaces: str | None = None,
        session: str = "review-1", round_number: int | None = 1, root: Path = ROOT,
        artifact_version: str | None = None, minutes_range: tuple[float, float] | None = None):
    if category not in CATEGORIES or method not in ("timed", "estimated", "missing"):
        raise ValueError("Invalid category or measurement method")
    if (not activity.strip() or not reviewer.strip() or not session.strip() or
            (round_number is not None and round_number < 1)):
        raise ValueError("Activity, reviewer, and session are required; a reported revision round must be positive")
    if method == "missing" and (minutes is not None or minutes_range is not None):
        raise ValueError("Missing reports cannot have a duration")
    if minutes_range is not None:
        if method != "estimated" or minutes is not None:
            raise ValueError("A range requires method estimated and no point duration")
        if (len(minutes_range) != 2 or
                any(not math.isfinite(value) or value < 0 for value in minutes_range) or
                minutes_range[0] > minutes_range[1]):
            raise ValueError("Report a finite nonnegative range with lower <= upper")
    elif method != "missing" and (minutes is None or not math.isfinite(minutes) or minutes < 0):
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
    if minutes_range is not None:
        row["active_minutes_range"] = {"lower": minutes_range[0], "upper": minutes_range[1]}
    path = root / "expert/time-log.jsonl"
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    return row


def minute_totals(rows):
    """Sum reported bounds without converting a range to an invented point estimate."""
    bounds = []
    has_range = False
    for row in rows:
        if row.get("active_minutes_range") is not None:
            bounds.append(row["active_minutes_range"])
            has_range = True
        elif row["active_minutes"] is not None:
            bounds.append({"lower": row["active_minutes"], "upper": row["active_minutes"]})
    if not bounds:
        return None, None, 0
    total = {key: sum(bound[key] for bound in bounds) for key in ("lower", "upper")}
    return None if has_range else total["lower"], total, len(bounds)


def summary(root: Path = ROOT):
    rows = records(root)
    superseded = {r["replaces"] for r in rows if r.get("replaces")}
    active = [r for r in rows if r["id"] not in superseded]
    included = [r for r in active if r["category"] in PREPARATION]
    total, total_range, _ = minute_totals(active)
    preparation, preparation_range, reported_count = minute_totals(included)
    mixed, mixed_range, _ = minute_totals([r for r in active if r["category"] == "mixed"])
    categories = {c: minute_totals([r for r in active if r["category"] == c]) for c in CATEGORIES}
    status = read_json(root / "reference/approval.json")
    approved = status["status"] == "approved" and status["review_version"] == review_version(root)
    return {
        "unit": "self-reported active person-minutes per practice pair",
        "reported_total_active_minutes": total,
        "reported_total_active_minutes_range": total_range,
        "reported_preparation_minutes": preparation,
        "reported_preparation_minutes_range": preparation_range,
        "reported_mixed_preparation_and_tooling_minutes": mixed,
        "reported_mixed_preparation_and_tooling_minutes_range": mixed_range,
        "missing_reports": len(included) - reported_count,
        "measurement_status": (
            "no reports yet" if not active else
            "combined preparation and tooling reported; case-preparation subtotal unknown" if mixed_range and not reported_count else
            "reported work only; check category coverage and missing entries"),
        "human_approved_current_version": approved,
        "by_category": {c: value[0] for c, value in categories.items()},
        "by_category_ranges": {c: value[1] for c, value in categories.items()},
        "review_sessions": len({(r["reviewer"], r["review_session"]) for r in included}),
        "revision_rounds": sorted({r["revision_round"] for r in included if r["revision_round"] is not None}),
        "estimated_reports": sum(r["method"] == "estimated" for r in active),
        "timed_reports": sum(r["method"] == "timed" for r in active),
        "note": "Ranges sum reported bounds, assuming activities do not overlap; no midpoint or missing effort is inferred. "
                "Mixed, tooling, and feedback-review reports are excluded from the case-preparation subtotal. "
                "Review-session and revision counts describe log groupings, not verified numbers of work sittings or correction passes. "
                "Unknown duration does not mean zero effort. Agent runtime is not human attention. "
                "This does not measure net savings.",
    }


def approve(reviewer: str, minutes: float, method: str, root: Path = ROOT):
    row = log(activity="Final approval of both cases, their diagnoses, and feedback guide",
              category="approval", reviewer=reviewer, minutes=minutes, method=method, root=root)
    status = {"status": "approved", "reviewer": reviewer, "review_version": review_version(root),
              "approved_at": now(), "attention_report_id": row["id"]}
    write_json(root / "reference/approval.json", status)
    return status
