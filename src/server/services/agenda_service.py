import re
import xml.etree.ElementTree as ET

import requests


class AgendaService:
    def __init__(self, env):
        self.xml_file = env.get("XML_FILE")
        self.ntfy_url = env.get("NTFY_URL")
        self.keys = [key.strip().lower() for key in env.get("KEYS", "").split(",") if key.strip()]

    def events(self):
        tree = ET.parse(self.xml_file)
        events = []
        for programme in tree.getroot().findall("programme"):
            title = (programme.findtext("title") or "").replace("PROXIMAMENTE: ", "")
            if self.keys and not any(key in title.lower() for key in self.keys):
                continue
            match = re.search(
                r"\[(?P<hora>\d{2}:\d{2})\]\s*(?P<torneo>.*?):\s*"
                r"(?P<equipos>[^;]+)(?:\s*;\s*(?P<canal>[^|]*))?",
                title,
            )
            if match:
                events.append({
                    "hora": match.group("hora"),
                    "torneo": match.group("torneo"),
                    "equipos": match.group("equipos").strip(),
                    "canal": (match.group("canal") or "").strip(),
                })
        unique = {f"{event['hora']}_{event['equipos']}": event for event in events}
        return sorted(unique.values(), key=lambda event: event["hora"])

    def update_ntfy(self):
        if not self.ntfy_url:
            return "NTFY no configurado; se omite el envío."
        events = self.events()
        if not events:
            return "No hay eventos para enviar a NTFY."
        message = "\n".join(f"{event['hora']} | {event['equipos']}" for event in events)
        response = requests.post(self.ntfy_url, data=message.encode("utf-8"), headers={"Title": "Grilla Deportiva"}, timeout=30)
        response.raise_for_status()
        return "Actualización enviada a NTFY."
