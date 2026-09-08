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
        links = self._read_m3u_links()
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
            match = re.search(r"\[(\d{2}:\d{2})\]\s*(.*)", title)
            if not match:
                continue
            channel_id = programme.get("channel")
            result.append(Channel(
                hora=match.group(1),
                nombre=match.group(2).replace("PROXIMAMENTE: ", "").strip(),
                link=links.get(channel_id, ""),
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

    def _read_m3u_links(self):
        links = {}
        current_id = None
        with open(self.m3u_path, encoding="utf-8") as playlist:
            for line in playlist:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r'tvg-id="([^"]+)"', line)
                    current_id = match.group(1) if match else None
                elif current_id and line and not line.startswith("#"):
                    links[current_id] = line
                    current_id = None
        return links
