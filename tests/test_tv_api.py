import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TvApiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from server.api_service import app
        cls.client = app.test_client()

    def test_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["api_version"], "v1")

    def test_events_contract(self):
        response = self.client.get("/api/v1/events")
        self.assertEqual(response.status_code, 200)
        payload = response.json
        self.assertIn("events", payload)
        self.assertGreater(len(payload["events"]), 0)
        event = payload["events"][0]
        self.assertTrue(event["id"])
        self.assertTrue(event["title"])
        self.assertIn("sources", event)
        self.assertTrue(event["sources"])
        self.assertTrue(event["sources"][0]["url"].endswith("&ip=186.65.68.74") or ".m3u8" in event["sources"][0]["url"])
        json.dumps(payload)

    def test_structured_catalog_preserves_multiple_sources(self):
        from server.services.channel_service import ChannelService
        with tempfile.TemporaryDirectory() as directory:
            events_path = Path(directory) / "events.json"
            events_path.write_text(json.dumps({"events": [{
                "id": "match-1",
                "title": "Match",
                "starts_at": "2026-09-09T20:00:00",
                "status": "available",
                "sources": [
                    {"id": "s1", "name": "ESPN", "url": "https://one.test/a.m3u8"},
                    {"id": "s2", "name": "Disney+", "url": "https://two.test/b.m3u8"},
                ],
            }]}), encoding="utf-8")
            events = ChannelService("missing.xml", "missing.m3u", events_path).list_events()
            self.assertEqual([source.name for source in events[0].sources], ["ESPN", "Disney+"])

    def test_legacy_files_group_same_event_sources(self):
        from server.services.channel_service import ChannelService
        with tempfile.TemporaryDirectory() as directory:
            xml_path = Path(directory) / "events.xml"
            m3u_path = Path(directory) / "events.m3u"
            xml_path.write_text("""<?xml version=\"1.0\"?><tv>
              <programme start=\"20260909200000 -0300\" channel=\"E01\"><title>[20:00] Liga: Equipo A vs Equipo B ; ESPN</title></programme>
              <programme start=\"20260909200000 -0300\" channel=\"E02\"><title>[20:00] Liga: Equipo A vs Equipo B ; Disney+</title></programme>
            </tv>""", encoding="utf-8")
            m3u_path.write_text("""#EXTM3U
#EXTINF:-1 tvg-id=\"E01\",E01
https://one.test/espn.m3u8
#EXTINF:-1 tvg-id=\"E02\",E02
https://two.test/disney.m3u8
""", encoding="utf-8")
            events = ChannelService(xml_path, m3u_path).list_events()
            self.assertEqual(len(events), 1)
            self.assertEqual({source.url for source in events[0].sources}, {
                "https://one.test/espn.m3u8", "https://two.test/disney.m3u8"
            })


if __name__ == "__main__":
    unittest.main()
