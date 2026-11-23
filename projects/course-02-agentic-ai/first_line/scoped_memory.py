"""Scoped, source-backed memory for successive simulator shifts."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

DAY = timedelta(days=1)


@dataclass(frozen=True)
class Evidence:
    id: str
    incident: str
    component: str
    observed: datetime
    kind: Literal["tool", "document", "reported", "inference"]
    readers: frozenset[str]
    fact: str
    value: str | int | float
    owner_team: str


@dataclass(frozen=True)
class Lesson:
    id: str
    team: str
    author: str
    component: str
    condition: str
    text: str
    sources: tuple[str, ...]
    reviewed: datetime
    kind: Literal["clue", "note", "procedure"] = "clue"
    version: int = 1
    review_due: datetime | None = None


class ScopedMemory:
    """One incident workspace, shared by the trusted harness across shifts.

    Derived views are built on demand from source IDs and the current ACL.
    """

    def __init__(self):
        self.sources = {}
        self.lessons = {}
        self.delivered = {}
        self.conflicts = {}
        self.withdrawn = {}
        self.approved = {}
        self.deletions = []
        self.shifts = {}

    def open_shift(self, incident):
        """A workspace-unique shift ID. Two shifts of one incident never share source or lesson IDs."""
        self.shifts[incident] = self.shifts.get(incident, 0) + 1
        return f"{incident}/shift-{self.shifts[incident]}"

    def record(self, source):
        """Add one source. Repeating an identical record is a no-op; a different record never replaces it."""
        if self.sources.get(source.id) == source:
            return
        if source.id in self.sources or any(row["id"] == source.id for row in self.deletions):
            raise ValueError("Source IDs cannot be reused")
        self.sources[source.id] = source

    def evidence(self, principal, refs):
        return [self.sources[ref] for ref in refs
                if ref in self.sources and principal.id in self.sources[ref].readers]

    def save(self, principal, lesson):
        sources = self.evidence(principal, lesson.sources)
        if (lesson.team != principal.team or lesson.author != principal.id or not lesson.condition
                or not sources or len(sources) != len(lesson.sources)
                or any(s.component != lesson.component or s.observed > lesson.reviewed for s in sources)):
            raise ValueError("Lesson needs scoped, dated evidence and a condition")
        if lesson.kind == "procedure" and len({s.incident for s in sources}) < 2:
            raise ValueError("Procedure proposal needs two independent incidents")
        if self.lessons.get(lesson.id) == lesson:
            return
        if lesson.id in self.lessons:
            raise ValueError("Use a new lesson ID for a new edition")
        self.lessons[lesson.id] = lesson

    def publish(self, operator, edition, original_id):
        original = self.lessons[original_id]
        self.require_operator(operator, original.team)
        if edition.team == original.team or edition.kind != "clue":
            raise ValueError("Publication needs a separate recipient clue")
        # The trusted operator creates an evidence-backed edition. Recipient
        # access to every cited source is checked again at delivery.
        # A published edition renders only recipient-readable structured evidence.
        self.save(replace(operator, team=edition.team), replace(edition, text="Check the cited observations."))

    @staticmethod
    def require_operator(actor, team):
        if (actor.team != team or actor.role != "incident-manager"
                or "manage_memory" not in actor.rights):
            raise PermissionError("Operator authority required")

    def approve(self, operator, lesson_id):
        lesson = self.lessons[lesson_id]
        self.require_operator(operator, lesson.team)
        if (lesson.kind != "procedure" or lesson.review_due is None or lesson.review_due <= lesson.reviewed
                or len(self.evidence(operator, lesson.sources)) != len(lesson.sources)):
            raise ValueError("Approval needs a procedure and future review date")
        self.approved[lesson_id] = lesson

    def revoke(self, operator, lesson_id):
        self.require_operator(operator, self.lessons[lesson_id].team)
        self.approved.pop(lesson_id, None)

    def review(self, principal, lesson_id, now, conditions):
        lesson = self.lessons[lesson_id]
        if (lesson.kind != "clue" or principal.team != lesson.team
                or conditions.get(lesson.condition, 0) <= 0
                or len(self.evidence(principal, lesson.sources)) != len(lesson.sources)
                or now < lesson.reviewed):
            raise ValueError("Review requires accessible evidence and current conditions")
        self.lessons[lesson_id] = replace(lesson, reviewed=now)

    def claims(self, principal, incident):
        """Unwithdrawn team claims that a restart started recovery in `incident`."""
        return [key for key, lesson in self.lessons.items()
                if lesson.team == principal.team and lesson.condition == "restart_started_recovery"
                and key not in self.withdrawn
                and incident in {s.incident for s in self.evidence(principal, lesson.sources)}]

    def incident_sources(self, principal, incident, fact):
        return [key for key, source in self.sources.items()
                if source.incident == incident and source.fact == fact and principal.id in source.readers]

    def assess_restart_claim(self, principal, lesson_id, refs, now):
        """Classify the reference claim that a restart started latency recovery."""
        lesson = self.lessons.get(lesson_id)
        if (lesson is None or principal.team != lesson.team or lesson.kind != "clue"
                or lesson.condition != "restart_started_recovery" or lesson_id in self.withdrawn
                or len(self.evidence(principal, lesson.sources)) != len(lesson.sources)):
            return "unsupported"
        incident_ids = {s.incident for s in self.evidence(principal, lesson.sources)}
        sources = [s for s in self.evidence(principal, refs)
                   if s.incident in incident_ids and s.component == lesson.component]
        drops = [s for s in sources if s.kind in {"tool", "document"} and s.fact == "latency_drop"]
        restarts = [s for s in sources if s.kind in {"tool", "document"} and s.fact == "restart"]
        if (len(drops) == len(restarts) == 1 and drops[0].incident == restarts[0].incident
                and drops[0].observed < restarts[0].observed):
            self.withdrawn[lesson_id] = {"team": lesson.team, "withdrawn_at": now, "reason": "latency fell before restart",
                                         "sources": (drops[0].id, restarts[0].id)}
            self.conflicts.pop(lesson_id, None)
            return "contradiction"
        if drops or restarts:
            self.conflicts[lesson_id] = tuple(s.id for s in sources)
            return "possible_conflict"
        return "unsupported"

    def change_readers(self, actor, ref, readers):
        source = self.sources.get(ref)
        if source is None or not self.evidence(actor, (ref,)):
            return False
        self.require_operator(actor, source.owner_team)
        self.sources[ref] = replace(source, readers=frozenset(readers))
        return True

    def delete(self, actor, ref, now):
        if ref not in self.sources or not self.evidence(actor, (ref,)):
            return False
        self.require_operator(actor, self.sources[ref].owner_team)
        del self.sources[ref]
        for key, lesson in tuple(self.lessons.items()):
            if ref in lesson.sources:
                # Free text may contain a copy of the deleted source. Discard
                # the derived text and preserve independent observations.
                del self.lessons[key]
                self.approved.pop(key, None)
                self.conflicts.pop(key, None)
        for record in self.withdrawn.values():
            if ref in record["sources"]:
                record["sources"] = tuple(source for source in record["sources"] if source != ref)
                record["reason"] = "support withdrawn"
        self.conflicts = {key: tuple(source for source in refs if source != ref)
                          for key, refs in self.conflicts.items()}
        self.deletions.append({"id": ref, "time": now, "actor": actor.id, "reason": "operator deletion"})
        return True

    def lookup(self, principal, lesson_id, now, conditions, *, handover=None):
        lesson = self.lessons.get(lesson_id)
        if lesson is None or lesson.team != principal.team or lesson_id in self.withdrawn:
            return None
        sources = self.evidence(principal, lesson.sources)
        if len(sources) != len(lesson.sources) or lesson_id in self.conflicts:
            return None
        fit = conditions.get(lesson.condition, 0)
        if lesson.kind == "note":
            active = (lesson.id not in self.delivered or self.delivered[lesson.id] is handover) and now - lesson.reviewed < DAY
        elif lesson.kind == "clue":
            active = fit > 0 and now - lesson.reviewed < 7 * DAY
        else:
            active = fit > 0 and self.approved.get(lesson.id) == lesson and now < lesson.review_due
        if not active or now < lesson.reviewed:
            return None
        latest = max(s.observed for s in sources)
        return {"id": lesson.id, "component": lesson.component, "text": lesson.text,
                "condition": lesson.condition, "fit": fit, "sources": [s.id for s in sources],
                "evidence": [{"id": s.id, "kind": s.kind, "fact": s.fact, "value": s.value,
                              "observed": s.observed.isoformat()} for s in sources],
                "age_seconds": int((now - latest).total_seconds()), "kind": lesson.kind,
                "uncertainty": "Verify the condition with current evidence."}

    def search(self, principal, component, now, conditions):
        views = (self.lookup(principal, key, now, conditions) for key in self.lessons)
        return sorted((view for view in views if view is not None),
                      key=lambda view: (view["component"] != component, -view["fit"], view["age_seconds"]))

    def handover(self, principal, component, now, conditions, *, handover):
        views = self.search(principal, component, now, conditions)
        notes = [view for view in views if view["kind"] == "note" and view["component"] == component]
        self.delivered.update({view["id"]: handover for view in notes})
        return notes + [view for view in views if view["kind"] != "note"][:2]

    def correction(self, principal, lesson_id):
        record = self.withdrawn.get(lesson_id)
        if record is None or principal.team != record["team"]:
            return None
        refs = record["sources"]
        sources = self.evidence(principal, refs)
        if len(sources) != len(refs) or not sources:
            return None
        facts = {source.fact for source in sources}
        if facts == {"latency_drop", "restart"}:
            conclusion = "Latency fell before the restart. Its later effect is unknown."
        else:
            conclusion = "Retained observations no longer establish event order."
        result = {"conclusion": conclusion, "sources": [
            {"id": source.id, "fact": source.fact, "time": source.observed.isoformat()} for source in sources]}
        lesson = self.lessons.get(lesson_id)
        if (facts == {"latency_drop", "restart"} and lesson
                and len(self.evidence(principal, lesson.sources)) == len(lesson.sources)):
            result["withdrawn_claim"] = lesson.text
        return result
