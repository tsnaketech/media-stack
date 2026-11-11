"""Ensure the exported policy cannot silently accept non-French releases."""
import copy
import json
import tempfile
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
policy_setup = importlib.import_module("configure-french-profiles")
setup = importlib.import_module("configure-profilarr")


class FrenchPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"name": "1080p Français", "custom_format": "Audio français requis",
                       "minimum_score": 10000, "qualities": ["WEBDL-1080p"], "upgrades_allowed": False}
        self.profile = {"name": self.policy["name"], "id": 7, "minFormatScore": 10000,
                        "formatItems": [{"format": 9, "score": 10000}], "upgradeAllowed": False,
                        "items": [{"allowed": True, "quality": {"name": "WEBDL-1080p"}}]}
        self.cf = {"id": 9, "name": self.policy["custom_format"], "specifications": [
            {"implementation": "LanguageSpecification", "negate": False, "required": True,
             "fields": [{"name": "value", "value": 2}, {"name": "exceptLanguage", "value": False}]}]}

    def verify(self, profile=None, cf=None):
        api = Mock()
        api.call.side_effect = [[profile or self.profile], [cf or self.cf]]
        return policy_setup.verify_profile(api, self.policy)

    def test_french_required_profile_is_valid(self):
        self.assertEqual(self.verify()["id"], 7)

    def test_zero_minimum_cannot_make_french_optional(self):
        profile = copy.deepcopy(self.profile)
        profile["minFormatScore"] = 0
        with self.assertRaises(setup.SetupError):
            self.verify(profile=profile)

    def test_other_scores_cannot_bypass_french_requirement(self):
        profile = copy.deepcopy(self.profile)
        profile["formatItems"].append({"format": 10, "score": 10000})
        with self.assertRaises(setup.SetupError):
            self.verify(profile=profile)

    def test_excluding_french_is_rejected(self):
        cf = copy.deepcopy(self.cf)
        cf["specifications"][0]["negate"] = True
        with self.assertRaises(setup.SetupError):
            self.verify(cf=cf)

    def test_4k_cannot_be_enabled_in_1080p_policy(self):
        profile = copy.deepcopy(self.profile)
        profile["items"].append({"allowed": True, "quality": {"name": "WEBDL-2160p"}})
        with self.assertRaises(setup.SetupError):
            self.verify(profile=profile)

    def test_csv_selection_accepts_individually_quoted_names(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("1080p Français", "2160p Français"):
                (Path(directory) / ("french-" + name.split()[0] + ".json")).write_text(json.dumps({"name": name}))
            policies = policy_setup.selected_policies('"1080p Français","2160p Français"', Path(directory))
            self.assertEqual([p["name"] for p in policies], ["1080p Français", "2160p Français"])

    def test_unknown_and_duplicate_profiles_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for value in ('"Unknown"', '"1080p Français","1080p Français"', '"1080p Français",', '"unterminated'):
                with self.subTest(value=value), self.assertRaises(setup.SetupError):
                    policy_setup.selected_policies(value, Path(directory))

    def test_page_decoder_preserves_integer_ids_and_shared_references(self):
        value = setup.decode_page_data([{"id": 1, "items": 2}, 7, [3, 3], {"name": 4}, "French"])
        self.assertEqual(value["id"], 7)
        self.assertEqual(value["items"][0]["name"], "French")
        self.assertIs(value["items"][0], value["items"][1])


if __name__ == "__main__":
    unittest.main()
