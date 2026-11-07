from datetime import datetime

from .enums import IndexGenerationState, JobStage, JobStatus
from .errors import IngestionInvalidStateError
from .models import IngestionJob

ALLOWED_JOB_TRANSITIONS: frozenset[tuple[JobStatus, JobStatus]] = frozenset(
    {
        (JobStatus.QUEUED, JobStatus.PROCESSING),
        (JobStatus.PROCESSING, JobStatus.COMPLETED),
        (JobStatus.PROCESSING, JobStatus.FAILED),
        (JobStatus.PROCESSING, JobStatus.QUEUED),
        (JobStatus.FAILED, JobStatus.QUEUED),
    }
)

ALLOWED_GENERATION_TRANSITIONS: frozenset[tuple[IndexGenerationState, IndexGenerationState]] = (
    frozenset(
        {
            (IndexGenerationState.STAGED, IndexGenerationState.ACTIVE),
            (IndexGenerationState.STAGED, IndexGenerationState.FAILED),
            (IndexGenerationState.ACTIVE, IndexGenerationState.SUPERSEDED),
        }
    )
)


def validate_job_transition(current: JobStatus, target: JobStatus) -> None:
    if (current, target) not in ALLOWED_JOB_TRANSITIONS:
        raise IngestionInvalidStateError()


def validate_generation_transition(
    current: IndexGenerationState, target: IndexGenerationState
) -> None:
    if (current, target) not in ALLOWED_GENERATION_TRANSITIONS:
        raise IngestionInvalidStateError()


def transition_job(
    job: IngestionJob,
    target: JobStatus,
    *,
    now: datetime,
    stage: JobStage | None = None,
    error_code: str | None = None,
) -> IngestionJob:
    """Return the job after a validated status change, applying the attempt and stage rules.

    A claim (``queued -> processing``) opens a new attempt and starts at ``validating``
    unless a stage is given. ``failed`` keeps the stage and requires an error code.
    """
    validate_job_transition(job.status, target)
    changes: dict[str, object] = {"status": target, "updated_at": now, "error_code": None}
    if target is JobStatus.PROCESSING:
        changes["attempt"] = job.attempt + 1
        changes["stage"] = stage or JobStage.VALIDATING
    elif target is JobStatus.FAILED:
        changes["stage"] = stage or job.stage
        changes["error_code"] = error_code
    else:
        changes["stage"] = None
    return IngestionJob.model_validate({**job.model_dump(), **changes})
