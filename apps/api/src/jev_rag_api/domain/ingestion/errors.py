class IngestionError(Exception):
    """Base class for stable ingestion errors.

    Instances carry only the machine code. They never carry document text, local paths,
    raw parser or provider errors, or secrets, so they are safe to map to public responses.
    """

    code = "ING_INTERNAL_ERROR"
    retryable = False

    def __init__(self) -> None:
        super().__init__(self.code)


class IngestionUnsupportedMediaTypeError(IngestionError):
    code = "ING_UNSUPPORTED_MEDIA_TYPE"


class IngestionFileTooLargeError(IngestionError):
    code = "ING_FILE_TOO_LARGE"


class IngestionInvalidDocumentError(IngestionError):
    code = "ING_INVALID_DOCUMENT"


class IngestionExtractionFailedError(IngestionError):
    code = "ING_EXTRACTION_FAILED"


class IngestionInvalidChunkError(IngestionError):
    code = "ING_INVALID_CHUNK"


class IngestionEmbeddingUnavailableError(IngestionError):
    code = "ING_EMBEDDING_UNAVAILABLE"
    retryable = True


class IngestionVectorStoreUnavailableError(IngestionError):
    code = "ING_VECTOR_STORE_UNAVAILABLE"
    retryable = True


class IngestionConflictError(IngestionError):
    """Idempotency, concurrency, or state conflict. Retry only after an explicit re-read."""

    code = "ING_CONFLICT"


class IngestionNotFoundError(IngestionError):
    code = "ING_NOT_FOUND"


class IngestionInvalidStateError(IngestionError):
    code = "ING_INVALID_STATE"


class IngestionIndexIncompatibleError(IngestionError):
    code = "ING_INDEX_INCOMPATIBLE"


class IngestionInternalError(IngestionError):
    code = "ING_INTERNAL_ERROR"


ERROR_CODES: frozenset[str] = frozenset(
    cls.code
    for cls in (
        IngestionUnsupportedMediaTypeError,
        IngestionFileTooLargeError,
        IngestionInvalidDocumentError,
        IngestionExtractionFailedError,
        IngestionInvalidChunkError,
        IngestionEmbeddingUnavailableError,
        IngestionVectorStoreUnavailableError,
        IngestionConflictError,
        IngestionNotFoundError,
        IngestionInvalidStateError,
        IngestionIndexIncompatibleError,
        IngestionInternalError,
    )
)
