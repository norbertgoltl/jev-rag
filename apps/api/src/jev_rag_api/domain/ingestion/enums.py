from enum import StrEnum


class DocumentLanguage(StrEnum):
    HU = "hu"
    EN = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStage(StrEnum):
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    FINALIZING = "finalizing"


class JobType(StrEnum):
    INGEST = "ingest"
    REINDEX = "reindex"
    DELETE = "delete"


class IndexGenerationState(StrEnum):
    STAGED = "staged"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class Visibility(StrEnum):
    STAGED = "staged"
    ACTIVE = "active"
    INACTIVE = "inactive"


class BlockKind(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"
    OTHER = "other"


class DistanceMetric(StrEnum):
    COSINE = "cosine"
    DOT = "dot"
    EUCLID = "euclid"
