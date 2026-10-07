"""Atomic batch completion, shared by in-process and optional Celery workers."""

from sqlalchemy import text


# MySQL evaluates SET assignments from left to right. Increment LAST so both
# completion checks see the old counter; otherwise the penultimate result can
# prematurely finish the batch. Terminal failures/cancellations stay terminal.
COMPLETE_SUBTASK_SQL = text("""
    UPDATE test_task
    SET status = CASE
            WHEN status IN ('failed', 'cancelled') THEN status
            WHEN completedSubtasks + 1 >= totalSubtasks THEN 'completed'
            WHEN status = 'pending' THEN 'running'
            ELSE status
        END,
        startedAt = COALESCE(startedAt, CURRENT_TIMESTAMP),
        completedAt = CASE
            WHEN status NOT IN ('failed', 'cancelled')
                 AND completedSubtasks + 1 >= totalSubtasks THEN CURRENT_TIMESTAMP
            ELSE completedAt
        END,
        completedSubtasks = completedSubtasks + 1
    WHERE id = :task_id AND isDelete = 0
""")
