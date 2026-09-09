from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Channel:
    hora: str
    torneo: str
    match: str
    canal: str
    link: str
    logo: str
    proximamente: bool

    @property
    def nombre(self):
        return f"{self.torneo}: {self.match}" if self.torneo else self.match


@dataclass(frozen=True)
class EventSource:
    id: str
    name: str
    url: str
    user_agent: Optional[str] = None


@dataclass(frozen=True)
class Event:
    id: str
    title: str
    starts_at: str
    status: str
    sources: List[EventSource]
    logo: str = ""
