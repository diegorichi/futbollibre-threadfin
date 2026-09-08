from dataclasses import dataclass


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
