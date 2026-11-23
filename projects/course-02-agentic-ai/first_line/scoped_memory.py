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
class Claim:
    """The explicit meaning of a reported restart claim. Code never infers it from the lesson text.

    `first_fall_after_restart` is a precise temporal claim: between `since` (when the delay was reported) and the
    restart of `target`, gateway latency did not fall. `restart_fixed_delay` is a broad causal attribution. Readings
    can contradict the first; they can neither establish nor disprove the second."""
    meaning: Literal["first_fall_after_restart", "restart_fixed_delay"]
    incident: str
    target: str
    since: datetime


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
    claim: Claim | None = None


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
        """Unwithdrawn team restart claims about `incident` whose own sources the principal can read."""
        return [key for key, lesson in self.lessons.items()
                if lesson.team == principal.team and lesson.claim is not None and lesson.claim.incident == incident
                and key not in self.withdrawn and len(self.evidence(principal, lesson.sources)) == len(lesson.sources)]

    def incident_sources(self, principal, incident, fact):
        return [key for key, source in self.sources.items()
                if source.incident == incident and source.fact == fact and principal.id in source.readers]

    def timeline(self, principal, claim, component, refs):
        """Readable tool or document observations for the claim's incident and component: latency readings from
        `since` on, in time order, and the receipts for a restart of the claimed target. Each fall is two readings,
        the later strictly lower, placed before the restart only if it ends before the recorded restart minute."""
        sources = [s for s in self.evidence(principal, refs) if s.incident == claim.incident
                   and s.component == component and s.kind in {"tool", "document"}]
        readings = sorted((s for s in sources if s.fact == "latency_ms" and s.observed >= claim.since),
                          key=lambda s: (s.observed, s.id))
        restarts = [s for s in sources if s.fact == "restart" and s.value == claim.target]
        restart = restarts[0] if len(restarts) == 1 else None
        falls = [{"from": a, "to": b, "before_restart": restart is not None and b.observed < restart.observed}
                 for a, b in zip(readings, readings[1:]) if b.observed > a.observed and b.value < a.value]
        return {"readings": readings, "restart": restart, "falls": falls}

    def assess_restart_claim(self, principal, lesson_id, refs, now):
        """Classify sourced readings against one restart claim, by its explicit meaning.

        A recorded fall before the single recorded restart of the claimed target directly contradicts
        `first_fall_after_restart`, which is withdrawn. Against `restart_fixed_delay` the same evidence is only a
        possible conflict: it stays flagged and is not relied on. Falls whose order against the restart is
        unknown flag the temporal claim. Anything else changes nothing."""
        lesson = self.lessons.get(lesson_id)
        if (lesson is None or lesson.claim is None or principal.team != lesson.team or lesson_id in self.withdrawn
                or len(self.evidence(principal, lesson.sources)) != len(lesson.sources)):
            return "unsupported"
        found = self.timeline(principal, lesson.claim, lesson.component, refs)
        ids = tuple(s.id for s in found["readings"]) + ((found["restart"].id,) if found["restart"] else ())
        early = [fall for fall in found["falls"] if fall["before_restart"]]
        if lesson.claim.meaning == "first_fall_after_restart" and early:
            self.withdrawn[lesson_id] = {"team": lesson.team, "claim": lesson.claim, "component": lesson.component,
                                         "withdrawn_at": now, "sources": ids,
                                         "reason": "a sourced latency fall precedes the recorded restart"}
            self.conflicts.pop(lesson_id, None)
            return "contradiction"
        if early or (lesson.claim.meaning == "first_fall_after_restart" and found["falls"] and not found["restart"]):
            self.conflicts[lesson_id] = {"team": lesson.team, "claim": lesson.claim, "component": lesson.component,
                                         "flagged_at": now, "sources": ids,
                                         "reason": "readings neither establish nor rule out the claim"}
            return "possible_conflict"
        return "unsupported"

    def claim_view(self, principal, lesson_id, record, status):
        """The retained observations behind a withdrawal or flag, with their times and values. Nothing if the
        principal is outside the team or cannot read every retained source."""
        if (record is None or principal.team != record["team"]
                or len(self.evidence(principal, record["sources"])) != len(record["sources"])):
            return None
        claim = record["claim"]
        found = self.timeline(principal, claim, record["component"], record["sources"])
        restart = found["restart"]
        def told(falls):
            return "; ".join(f"from {fall['from'].value:g} ms at {fall['from'].observed:%H:%M} to "
                             f"{fall['to'].value:g} ms at {fall['to'].observed:%H:%M}" for fall in falls)

        early = [fall for fall in found["falls"] if fall["before_restart"]]
        later = [fall for fall in found["falls"] if not fall["before_restart"]]
        if restart is None:
            order = ((f"Latency fell {told(later)}. " if later else "")
                     + "No retained record gives the restart time, so the order of events is not established.")
        else:
            order = (f"Before the restart of {restart.value} at {restart.observed:%H:%M}, latency fell {told(early)}."
                     if early else f"No fall is recorded before the restart of {restart.value} at "
                                   f"{restart.observed:%H:%M}.")
            order += f" From the restart minute on, it fell {told(later)}." if later else ""
        if status == "withdrawn":
            outcome = ("The claim that latency first fell after the restart stays withdrawn. "
                       "Whether the restart helped later is not established.")
        else:
            outcome = ("These readings neither establish nor rule out that the restart helped. "
                       "The claim stays flagged; do not rely on it for the current decision.")
        view = {"claim": lesson_id, "meaning": claim.meaning, "status": status,
                "conclusion": f"{order} {outcome}", "reason": record["reason"],
                "readings": [{"id": s.id, "time": s.observed.isoformat(), "latency_ms": s.value}
                             for s in found["readings"]],
                "restart": restart and {"id": restart.id, "time": restart.observed.isoformat(),
                                        "target": restart.value}}
        lesson = self.lessons.get(lesson_id)
        if lesson and len(self.evidence(principal, lesson.sources)) == len(lesson.sources):
            view["claim_text"] = lesson.text
        return view

    def correction(self, principal, lesson_id):
        return self.claim_view(principal, lesson_id, self.withdrawn.get(lesson_id), "withdrawn")

    def flag(self, principal, lesson_id):
        return self.claim_view(principal, lesson_id, self.conflicts.get(lesson_id), "flagged")

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
        # Withdrawn and flagged claims keep their status: deletion never reinstates a claim. Only the
        # retained sources are cited afterwards.
        for record in (*self.withdrawn.values(), *self.conflicts.values()):
            record["sources"] = tuple(source for source in record["sources"] if source != ref)
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
