"""Golden pre-redesign UI contract: keep every existing control and option.

The fixture was captured before the converter restyle, not generated from the
new layout. Runtime approval and media behavior are covered by the GUI suites.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InterfaceContract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.labels = []
        self.options = {}
        self.form = None
        self.select = None
        self.external_assets = []
        self.inline_handlers = []
        self.duplicate_ids = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "form":
            self.form = attrs.get("id")
        if "id" in attrs:
            if attrs["id"] in self.ids:
                self.duplicate_ids.append(attrs["id"])
            self.ids[attrs["id"]] = {"tag": tag,
                "attrs": {k: v for k, v in attrs.items() if k != "class"},
                "form": self.form}
        if tag == "label":
            self.labels.append(attrs.get("for"))
        if tag == "select":
            self.select = attrs.get("id")
            self.options[self.select] = []
        if tag == "option" and self.select is not None:
            self.options[self.select].append({"value": attrs.get("value"), "text": ""})
        if tag in ("script", "link", "img", "iframe"):
            location = attrs.get("src", attrs.get("href", ""))
            if location.startswith(("http:", "https:", "//")):
                self.external_assets.append(location)
        self.inline_handlers.extend(k for k in attrs if k.startswith("on"))

    def handle_data(self, data):
        if self.select is not None and self.options[self.select]:
            self.options[self.select][-1]["text"] += data

    def handle_endtag(self, tag):
        if tag == "form":
            self.form = None
        if tag == "select":
            self.select = None


class UiPreservationTests(unittest.TestCase):
    def setUp(self):
        self.golden = json.loads((ROOT / "tests/fixtures/ui_contract_v1.json").read_text(encoding="utf-8"))
        self.ui = InterfaceContract()
        self.ui.feed((ROOT / "web/index.html").read_text(encoding="utf-8"))

    def test_all_existing_ids_constraints_forms_and_live_regions_survive(self):
        added = {"research-controls", "research-enabled", "research-help", "research-search",
                 "research-status", "research-preview", "saved-research", "saved-research-title",
                 "saved-research-content"}
        self.assertEqual(set(self.ui.ids) - set(self.golden["ids"]), added)
        self.assertEqual({key: self.ui.ids[key] for key in self.golden["ids"]}, self.golden["ids"])
        self.assertEqual(self.ui.duplicate_ids, [])
        self.assertEqual(self.ui.ids["notice"]["attrs"]["role"], "status")
        self.assertEqual(self.ui.ids["notice"]["attrs"]["aria-live"], "polite")
        for identity in ("job-content", "quote-section", "result-section", "revision-section"):
            self.assertIn("hidden", self.ui.ids[identity]["attrs"])

    def test_all_labels_existing_modes_and_explicit_api_mode_survive(self):
        self.assertEqual([item for item in self.ui.labels if item != "research-enabled"], self.golden["labels"])
        self.assertEqual(self.ui.labels.count("research-enabled"), 1)
        existing = {key: value for key, value in self.ui.options.items() if key != "model-mode"}
        self.assertEqual(existing, {key: value for key, value in self.golden["options"].items() if key != "model-mode"})
        self.assertEqual(self.ui.options["model-mode"][:4], self.golden["options"]["model-mode"])
        self.assertEqual(self.ui.options["model-mode"][4:], [
            {"value": "openai_api", "text": "실제 AI 기획·대본 · GPT-6.1 Sol API"}])
        self.assertNotIn("selected", self.ui.ids["model-mode"]["attrs"])
        for identity in self.ui.labels:
            self.assertIn(identity, self.ui.ids)
        self.assertEqual(self.ui.ids["research-enabled"]["attrs"]["type"], "checkbox")
        self.assertNotIn("checked", self.ui.ids["research-enabled"]["attrs"])
        self.assertIn("disabled", self.ui.ids["research-search"]["attrs"])

    def test_no_remote_assets_or_inline_handlers_bypass_existing_behavior(self):
        self.assertEqual(self.ui.external_assets, [])
        self.assertEqual(self.ui.inline_handlers, [])
        self.assertEqual(self.ui.ids["video"]["attrs"]["preload"], "metadata")
        self.assertIn("controls", self.ui.ids["video"]["attrs"])


if __name__ == "__main__":
    unittest.main()
