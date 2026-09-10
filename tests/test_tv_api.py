import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_app_update_contract(self):
        response = self.client.get("/api/v1/app")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json["version_code"], 1)
        self.assertTrue(response.json["version_name"])
        self.assertEqual(response.json["apk_url"], "/downloads/futbol-tv.apk")

    def test_tv_app_page_contains_installation_instructions(self):
        response = self.client.get("/tvapp")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Primera instalación", response.text)
        self.assertIn("Actualizaciones", response.text)
        self.assertIn("/downloads/futbol-tv.apk", response.text)

    def test_server_menu_links_tv_app(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/tvapp"', response.text)

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
            self.assertEqual(events[0].starts_at, "2026-09-09T20:00:00-03:00")
            self.assertEqual({source.url for source in events[0].sources}, {
                "https://one.test/espn.m3u8", "https://two.test/disney.m3u8"
            })

    def test_event_time_uses_visible_title_time_when_xml_start_is_generation_time(self):
        from server.services.channel_service import ChannelService
        self.assertEqual(
            ChannelService._iso_start("20260909130411 -0300", "11:00"),
            "2026-09-09T11:00:00-03:00",
        )

    def test_agenda_hour_rolls_back_to_previous_day_after_midnight(self):
        import futbol
        from datetime import datetime

        ahora = datetime(2026, 9, 10, 0, 38)
        self.assertEqual(
            futbol._hora_mas_cercana("21:30", ahora),
            datetime(2026, 9, 9, 21, 30),
        )

    def test_unavailable_placeholder_is_not_an_event_source(self):
        from server.services.channel_service import ChannelService
        with tempfile.TemporaryDirectory() as directory:
            xml_path = Path(directory) / "events.xml"
            m3u_path = Path(directory) / "events.m3u"
            xml_path.write_text("""<?xml version=\"1.0\"?><tv>
              <programme start=\"20260909200000 -0300\" channel=\"E01\"><title>[20:00] Partido informativo ; Sin señal</title></programme>
              <programme start=\"20260909200000 -0300\" channel=\"E02\"><title>[20:00] Partido real ; ESPN</title></programme>
            </tv>""", encoding="utf-8")
            m3u_path.write_text("""#EXTM3U
#EXTINF:-1 tvg-id=\"E01\",E01
https://demo.unified-streaming.com/k8s/live/scte35.isml/.m3u8
#EXTINF:-1 tvg-id=\"E02\",E02
https://one.test/real.m3u8
""", encoding="utf-8")
            events = ChannelService(xml_path, m3u_path).list_events()
            self.assertEqual([event.title for event in events], ["Partido real"])

    def test_extra_site_upsert_preserves_existing_grid(self):
        import futbol

        with tempfile.TemporaryDirectory() as directory:
            xml_path = Path(directory) / "events.xml"
            m3u_path = Path(directory) / "events.m3u"
            xml_path.write_text("""<?xml version=\"1.0\"?><tv>
              <programme start=\"20260909200000 -0300\" channel=\"E01\"><title>[20:00] MLS: Partido anterior ; ESPN</title></programme>
              <programme start=\"20260909210000 -0300\" channel=\"E02\"><title>PROXIMAMENTE: [21:00] AEW: Lucha libre ; TNT</title></programme>
            </tv>""", encoding="utf-8")
            m3u_path.write_text("""#EXTM3U
#EXTINF:-1 tvg-id=\"E01\",E01
https://old.test/partido.m3u8
#EXTINF:-1 tvg-id=\"E02\",E02
https://demo.unified-streaming.com/k8s/live/scte35.isml/.m3u8
""", encoding="utf-8")

            with patch.object(futbol, "M3U_FILE", str(m3u_path)), \
                    patch.object(futbol, "XML_FILE", str(xml_path)):
                active, upcoming = futbol._fusionar_sitio_extra(
                    [{"nombre": "MLS: Chicago Fire vs Inter Miami", "hora": "20:30", "canal": "Apple TV", "logo": "", "url": "https://new.test/mls.m3u8"}],
                    [],
                )

            self.assertEqual(
                [item["nombre"] for item in active],
                ["MLS: Partido anterior", "MLS: Chicago Fire vs Inter Miami"],
            )
            self.assertEqual([item["nombre"] for item in upcoming], ["AEW: Lucha libre"])
            self.assertEqual(active[0]["_stream_result"], ("https://old.test/partido.m3u8", "persistido"))


if __name__ == "__main__":
    unittest.main()
