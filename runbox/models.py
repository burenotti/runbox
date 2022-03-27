from datetime import timedelta
from pydantic import BaseModel
from typing import Literal, Sequence

__all__ = [
    'File', 'DockerProfile', 'Limits'
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
    workdir_mount: str
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
