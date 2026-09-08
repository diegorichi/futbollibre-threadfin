import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from server.models.channel import Channel


class ChannelService:
    def __init__(self, xml_path, m3u_path):
        self.xml_path = xml_path
        self.m3u_path = m3u_path

    def list_channels(self):
        entries = self._read_m3u_entries()
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        channels = {
            child.get("id"): (child.findtext("display-name") or child.get("id"))
            for child in root.findall("channel")
        }
        result = []
        for programme in root.findall("programme"):
            title = programme.findtext("title") or ""
            if "Slot Libre" in title:
                continue
            title_match = re.search(r"\[(\d{2}:\d{2})\]\s*(.*)", title)
            if not title_match:
                continue
            channel_id = programme.get("channel")
            description = title_match.group(2).strip()
            proximamente = description.startswith("PROXIMAMENTE:")
            description = description.replace("PROXIMAMENTE: ", "", 1).strip()
            event_and_channel = description.split(";", 1)
            event_name = event_and_channel[0].strip()
            channel_name = event_and_channel[1].strip() if len(event_and_channel) > 1 else ""
            tournament_and_match = event_name.split(":", 1)
            result.append(Channel(
                hora=title_match.group(1),
                torneo=tournament_and_match[0].strip() if len(tournament_and_match) > 1 else "",
                match=tournament_and_match[-1].strip(),
                canal=channel_name,
                link=entries.get(channel_id, {}).get("link", ""),
                logo=(programme.find("icon").get("src") if programme.find("icon") is not None else entries.get(channel_id, {}).get("logo", "")),
                proximamente=proximamente,
            ))
        return sorted(result, key=lambda item: item.hora)

    def source_update_dates(self):
        return {
            "xml": self._format_mtime(self.xml_path),
            "m3u": self._format_mtime(self.m3u_path),
        }

    @staticmethod
    def _format_mtime(path):
        try:
            return datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except FileNotFoundError:
            return "No disponible"

    def _read_m3u_entries(self):
        entries = {}
        current_id = None
        with open(self.m3u_path, encoding="utf-8") as playlist:
            for line in playlist:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r'tvg-id="([^"]+)"', line)
                    current_id = match.group(1) if match else None
                    if current_id:
                        logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                        entries[current_id] = {"logo": logo_match.group(1) if logo_match else ""}
                elif current_id and line and not line.startswith("#"):
                    entries[current_id]["link"] = line
                    current_id = None
        return entries
