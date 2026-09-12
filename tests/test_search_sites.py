import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class SearchSitesTest(unittest.TestCase):
    def test_uses_browser_headers_and_configured_engine(self):
        import search_sites

        responses = [{"results": [{"url": "https://futbol.example/"}]}]

        with patch.object(search_sites, "SEARCH_URL", "http://searx.test/search"), \
                patch.object(search_sites, "ENGINE", "duckduckgo"), \
                patch.object(search_sites, "QUERY", "futbol libre"), \
                patch.object(search_sites, "build_opener") as build_opener:
            opener = build_opener.return_value
            opener.open.side_effect = [Response(payload) for payload in responses]

            self.assertEqual(search_sites.fetch_urls(), ["https://futbol.example/"])

        request = opener.open.call_args_list[0].args[0]
        self.assertIn("engines=duckduckgo", request.full_url)
        self.assertIn("q=futbol+libre", request.full_url)
        self.assertEqual(request.get_header("Accept-language"), "es-US,es;q=0.9,en-US;q=0.8,en;q=0.7")
        self.assertIn("Macintosh", request.get_header("User-agent"))

    def test_identifies_loaded_sites_without_events(self):
        import futbol

        self.assertEqual(
            futbol.urls_sin_eventos(
                ["https://ok.test", "https://empty.test", "https://error.test"],
                [
                    {"url": "https://ok.test", "eventos": 2},
                    {"url": "https://empty.test", "eventos": 0},
                ],
            ),
            ["https://empty.test"],
        )


if __name__ == "__main__":
    unittest.main()
