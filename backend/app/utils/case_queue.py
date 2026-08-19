"""Pure helpers for the doctor queue's stable keyset pagination."""


def build_cases_cursor_filter(
    *,
    before_time: str,
    before_priority: int,
    before_needs_review: bool | None,
    before_id: str | None,
) -> str:
    """Build the PostgREST keyset predicate for the doctor queue.

    The queue is ordered by triage priority ASC, needs_review DESC, created_at
    DESC, and id DESC. The boolean cursor is optional for one-release backward
    compatibility; new clients always send it after receiving it in the first
    response.
    """
    clauses = [f"triage_priority.gt.{before_priority}"]

    if before_needs_review is None:
        # Legacy cursor shape used before needs_review became a sort key.
        clauses.append(
            f"and(triage_priority.eq.{before_priority},created_at.lt.{before_time})"
        )
        if before_id is not None:
            clauses.append(
                f"and(triage_priority.eq.{before_priority},created_at.eq.{before_time},id.lt.{before_id})"
            )
        return ",".join(clauses)

    review_literal = "true" if before_needs_review else "false"
    if before_needs_review:
        # All unflagged cases follow a flagged cursor regardless of timestamp.
        clauses.append(
            f"and(triage_priority.eq.{before_priority},needs_review.lt.{review_literal})"
        )

    clauses.append(
        f"and(triage_priority.eq.{before_priority},needs_review.eq.{review_literal},"
        f"created_at.lt.{before_time})"
    )
    if before_id is not None:
        clauses.append(
            f"and(triage_priority.eq.{before_priority},needs_review.eq.{review_literal},"
            f"created_at.eq.{before_time},id.lt.{before_id})"
        )
    return ",".join(clauses)
