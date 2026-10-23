from typing import Literal

from pydantic import BaseModel, ConfigDict


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LivenessResponse(ResponseModel):
    status: Literal["alive"] = "alive"


class UpDependencies(ResponseModel):
    qdrant: Literal["up"] = "up"


class DownDependencies(ResponseModel):
    qdrant: Literal["down"] = "down"


class ReadinessResponse(ResponseModel):
    status: Literal["ready"] = "ready"
    dependencies: UpDependencies


class NotReadyResponse(ResponseModel):
    status: Literal["not_ready"] = "not_ready"
    dependencies: DownDependencies


class SystemStatusResponse(ResponseModel):
    service: Literal["api"] = "api"
    status: Literal["ok"] = "ok"
