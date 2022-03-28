import pathlib
from datetime import timedelta, datetime
from pydantic import BaseModel, Field
from typing import Literal, Sequence

__all__ = [
    'File', 'DockerProfile',
    'Limits', 'SandboxState'
]


class File(BaseModel):
    name: str
    content: str | bytes
    type: Literal["binary", "text"] = "text"

    def content_bytes(self):
        if self.type == 'binary':
            return self.content
        else:
            return self.content.encode('utf-8')


class DockerProfile(BaseModel):
    image: str
    workdir_mount: pathlib.Path
    exec: str
    user: str

    def cmd(self, files: Sequence[File]) -> list[str]:
        return [self.exec, *(file.name for file in files)]


class Limits(BaseModel):
    time: timedelta = timedelta(seconds=1)
    memory_mb: int = 64
    cpu_count: int = 1
    disk_space_mb: int = 256

    @property
    def memory_bytes(self) -> int:
        return self.memory_mb * 1024**2


class SandboxState(BaseModel):
    status: str = Field(..., alias="Status")
    exit_code: int | None = Field(None, alias="ExitCode")
    started_at: datetime = Field(..., alias="StartedAt")
    finished_at: datetime | None = Field(None, alias="FinishedAt")
    memory_limit: bool = Field(..., alias="OOMKilled")
    cpu_limit: bool = Field(..., alias="CpuLimit")

    @property
    def duration(self) -> timedelta:
        if self.finished_at:
            return self.finished_at - self.started_at
        else:
            return timedelta(seconds=-1)
