from typing import TypeVar, Generic, TYPE_CHECKING

from pydantic import BaseModel

from ..models import Limits

ParamsType = TypeVar('ParamsType', bound=BaseModel)

if TYPE_CHECKING:
    from .stages import BuildStage


class StageError(Generic[ParamsType], Exception):

    def __init__(
        self, message: str,
        key: str,
        params: ParamsType,
        stage: "BuildStage",
    ):
        full_message = f"Error in stage {key}: {message}"
        super().__init__(full_message, key, params, stage)
        self.key = key
        self.params: ParamsType = params
        self.stage = stage


class UseSandboxError(StageError["UseSandbox.Params"]):
    pass


class NonZeroExitCodeError(UseSandboxError):

    def __init__(
        self, exit_code: int,
        key: str,
        params: ParamsType,
        stage: "BuildStage",
    ):
        message = f"Sandbox finished with non-zero exit code ({exit_code})"
        super().__init__(message, key, params, stage)


class CpuLimitError(UseSandboxError):

    def __init__(
        self, limits: Limits,
        key: str,
        params: ParamsType,
        stage: "BuildStage",
    ):
        message = f"Sandbox has been killed due to time limit >{limits.time.total_seconds()}s"
        super().__init__(message, key, params, stage)


class MemoryLimitError(UseSandboxError):

    def __init__(
        self, limits: Limits,
        key: str,
        params: ParamsType,
        stage: "BuildStage",
    ):
        message = f"Sandbox has been killed due to memory limit >{limits.memory_mb}MB"
        super().__init__(message, key, params, stage)
