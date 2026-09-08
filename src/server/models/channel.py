from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    hora: str
    nombre: str
    link: str
