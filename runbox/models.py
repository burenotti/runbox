import itertools
import pathlib
import types
from datetime import timedelta, datetime
from typing import Literal, Sequence

from pydantic import BaseModel, Field

__all__ = [
    'File', 'DockerProfile',
    'Limits', 'SandboxState'
]

from runbox.utils import Placeholder


class File(BaseModel):
    name: str
    content: str | bytes
    type: Literal["binary", "text"] = "text"

    def content_bytes(self):
        """Encodes content of the file in utf-8 if it is a plain text

        :return: either unmodified binary or text encoded in utf-8
        :rtype: str | bytes
        """
        if self.type == 'binary':
            return self.content
        else:
            return self.content.encode('utf-8')


class DockerProfile(BaseModel):
    image: str
    workdir: pathlib.Path
    user: str
    cmd_template: list[str | types.EllipsisType | Placeholder] = Field(..., exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def cmd(self, files: Sequence[File]) -> list[str]:
        cmd = self.cmd_template.copy()
        unused = [True] * len(files)
        for idx, arg in enumerate(cmd):
            if isinstance(arg, Placeholder):
                try:
                    cmd[idx] = files[arg.arg_num].name
                    unused[arg.arg_num] = False
                except IndexError:
                    err = ValueError(f"Cannot bind argument {arg.arg_num}. "
                                     f"Have only {len(files)} files")
                    raise err from None

        if Ellipsis in cmd:
            idx = cmd.index(Ellipsis)
            cmd[idx:idx + 1] = itertools.compress((file.name for file in files), unused)

        return cmd


class Limits(BaseModel):
    time: timedelta = timedelta(seconds=1)
    memory_mb: int = 64
    cpu_count: int = 1
    disk_space_mb: int = 256

    @property
    def memory_bytes(self) -> int:
        return self.memory_mb * 1024 ** 2


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
