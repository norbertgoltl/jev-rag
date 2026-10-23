from pydantic import BaseModel, ConfigDict


class ValidationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    code: str


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    details: list[ValidationDetail] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail
    request_id: str
