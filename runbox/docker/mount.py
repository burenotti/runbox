from pathlib import Path

from aiodocker.volumes import DockerVolume
from pydantic import BaseModel


class Mount(BaseModel):
    volume: DockerVolume
    bind: Path
    readonly: bool = False

    class Config:
        arbitrary_types_allowed = True
        allow_mutation = False

    def dump(self) -> dict:
        return {
            "Target": str(self.bind),
            "Source": self.volume.name,
            "Type": "volume",
            "ReadOnly": self.readonly,
        }
