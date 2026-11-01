"""The vendor's measure of the come-back features: "% of customers who came back within 14 days".

Computed from real visits only. A customer counts once their first plate at the stand is at least
14 days old (so everybody had the full 14 days); they "came back" if they had another plate
within 14 days of the first. The weekly cohorts (by first-plate week) keep the before/after
comparison possible: the features' launch dates are in docs/return-visit-boosters.md.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from ..models import Visit, Workspace

WINDOW = timedelta(days=14)


def return_rate(session: Session, *, workspace: Workspace, now: datetime, weeks: int = 12) -> dict[str, Any]:
    visits: dict[int, list[datetime]] = defaultdict(list)
    for customer_id, at in session.exec(
        select(Visit.customer_id, Visit.created_at).where(Visit.workspace_id == workspace.id).order_by(Visit.created_at)
    ).all():
        visits[customer_id].append(at)

    eligible = returned = 0
    cohorts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for times in visits.values():
        first = times[0]
        if first > now - WINDOW:
            continue  # not 14 days old yet
        came_back = any(first < t <= first + WINDOW for t in times[1:])
        eligible += 1
        returned += came_back
        week = (first - timedelta(days=first.weekday())).date().isoformat()
        cohorts[week][0] += 1
        cohorts[week][1] += came_back
    recent = sorted(cohorts.items())[-weeks:]
    return {
        "percent": round(100 * returned / eligible) if eligible else None,
        "returned": returned,
        "customers": eligible,
        "weeks": [{"week": w, "customers": c, "returned": r} for w, (c, r) in recent],
    }
