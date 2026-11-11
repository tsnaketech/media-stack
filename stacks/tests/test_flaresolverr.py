"""Protect existing proxy settings and avoid unintended indexer changes."""
import copy
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
flare = importlib.import_module("configure-flaresolverr")


class FlareSolverrSetupTests(unittest.TestCase):
    def setUp(self):
        self.proxy = {"id": 7, "name": "FlareSolverr", "implementation": "FlareSolverr",
                      "tags": [1], "customSetting": "preserve", "fields": [
                          {"name": "host", "value": "http://flaresolverr:8191/"},
                          {"name": "requestTimeout", "value": 60}]}

    def test_existing_proxy_is_matched_without_duplicate(self):
        result = flare.find_proxy([self.proxy], "http://flaresolverr:8191")
        self.assertIs(result, self.proxy)

    def test_ambiguous_proxies_are_rejected(self):
        with self.assertRaises(flare.common.SetupError):
            flare.find_proxy([self.proxy, dict(self.proxy, id=8)], "http://flaresolverr:8191")

    def test_update_preserves_id_and_other_settings(self):
        original = copy.deepcopy(self.proxy)
        result = flare.proxy_payload({}, self.proxy, "http://flaresolverr:8191", 90, 3)
        self.assertEqual(result["id"], 7)
        self.assertEqual(result["customSetting"], "preserve")
        self.assertEqual(flare.field_value(result, "requestTimeout"), 90)
        self.assertEqual(result["tags"], [3])
        self.assertEqual(self.proxy, original)

    def test_blank_selection_never_tags_all_indexers(self):
        self.assertEqual(flare.selected_indexers([{"id": 1, "name": "Example"}], ""), [])

    def test_unknown_selection_is_rejected(self):
        with self.assertRaises(flare.common.SetupError):
            flare.selected_indexers([{"id": 1, "name": "Example"}], '"Unknown"')

    def test_selection_handles_spaces_and_commas_in_quoted_names(self):
        rows = [{"id": 1, "name": "First, indexer"}, {"id": 2, "name": "Second indexer"}]
        self.assertEqual(flare.selected_indexers(rows, '"First, indexer","Second indexer"'), rows)


if __name__ == "__main__":
    unittest.main()
