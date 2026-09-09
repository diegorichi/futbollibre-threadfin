import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from server.models.channel import Channel, Event, EventSource


class ChannelService:
    def __init__(self, xml_path, m3u_path, events_path=None):
        self.xml_path = xml_path
        self.m3u_path = m3u_path
        self.events_path = events_path

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

    def list_events(self):
        """Return the current dynamic event catalog for TV/mobile clients.

        XMLTV remains the source of event metadata and M3U remains the source
        of playable URLs.  The API exposes a structured contract instead of
        making clients parse either legacy file.
        """
        if self.events_path and Path(self.events_path).exists():
            return self._read_events_json()
        entries = self._read_m3u_entries()
        tree = ET.parse(self.xml_path)
        grouped = {}
        for programme in tree.getroot().findall("programme"):
            title = programme.findtext("title") or ""
            if "Slot Libre" in title:
                continue
            title_match = re.search(r"\[(\d{2}:\d{2})\]\s*(.*)", title)
            if not title_match:
                continue

            channel_id = programme.get("channel") or ""
            description = title_match.group(2).strip()
            is_upcoming = description.startswith("PROXIMAMENTE:")
            if is_upcoming:
                description = description.replace("PROXIMAMENTE:", "", 1).strip()
            event_name, separator, channel_name = description.partition(";")
            event_name = event_name.strip()
            channel_name = channel_name.strip() if separator else ""
            starts_at = self._iso_start(programme.get("start"), title_match.group(1))
            source_entry = entries.get(channel_id, {})
            url = source_entry.get("link", "")
            sources = []
            if url:
                source_name = channel_name or self._source_name(url, channel_id)
                sources.append(EventSource(
                    id=f"{channel_id.lower()}-1",
                    name=source_name,
                    url=url,
                    user_agent=source_entry.get("user_agent"),
                ))
            group_key = (re.sub(r"[^a-z0-9]+", " ", event_name.lower()).strip(), starts_at[:16])
            group = grouped.setdefault(group_key, {
                "id": self._event_id(event_name, starts_at, "event"),
                "title": event_name,
                "starts_at": starts_at,
                "status": "upcoming" if is_upcoming else "available",
                "sources": [],
            })
            if not is_upcoming and not sources:
                group["status"] = "unavailable"
            existing_urls = {source.url for source in group["sources"]}
            for source in sources:
                if source.url not in existing_urls:
                    group["sources"].append(source)
                    existing_urls.add(source.url)
            if group["sources"]:
                group["status"] = "available"
        events = [Event(**item) for item in grouped.values()]
        return sorted(events, key=lambda item: item.starts_at)

    def _read_events_json(self):
        with open(self.events_path, encoding="utf-8") as source:
            payload = json.load(source)
        events = []
        for raw_event in payload.get("events", []):
            sources = [EventSource(
                id=raw_source.get("id", f"source-{index}"),
                name=raw_source.get("name", f"Fuente {index}"),
                url=raw_source.get("url", ""),
                user_agent=raw_source.get("user_agent"),
            ) for index, raw_source in enumerate(raw_event.get("sources", []), start=1) if raw_source.get("url")]
            events.append(Event(
                id=raw_event.get("id", "event"),
                title=raw_event.get("title", "Evento"),
                starts_at=raw_event.get("starts_at", ""),
                status=raw_event.get("status", "unavailable"),
                sources=sources,
                logo=raw_event.get("logo", ""),
            ))
        return sorted(events, key=lambda item: item.starts_at)

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
                elif current_id and line.startswith("#EXTVLCOPT:http-user-agent="):
                    entries[current_id]["user_agent"] = line.split("=", 1)[1].strip('"')
                elif current_id and line and not line.startswith("#"):
                    entries[current_id]["link"] = line
                    current_id = None
        return entries

    @staticmethod
    def _iso_start(raw_value, fallback_time):
        if raw_value:
            match = re.match(r"(\d{14})\s*([+-]\d{4})?", raw_value)
            if match:
                value = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
                offset = match.group(2)
                if offset:
                    sign = 1 if offset[0] == "+" else -1
                    minutes = int(offset[1:3]) * 60 + int(offset[3:5])
                    value = value.replace(tzinfo=timezone(sign * timedelta(minutes=minutes)))
                else:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
        return f"{datetime.now().date().isoformat()}T{fallback_time}:00"

    @staticmethod
    def _event_id(title, starts_at, channel_id):
        normalized = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or channel_id.lower()
        return f"{normalized}-{starts_at[:10]}-{starts_at[11:16].replace(':', '')}"

    @staticmethod
    def _source_name(url, channel_id):
        path = urlparse(url).path.lower()
        known_names = ("disney+", "disney", "espn", "movistar+", "movistar", "max", "paramount")
        for name in known_names:
            if name.replace("+", "") in path.replace("+", ""):
                return name.title()
        return f"Fuente {channel_id.removeprefix('E') or '1'}"
