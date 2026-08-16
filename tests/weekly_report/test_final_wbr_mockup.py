from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
MOCKUP = ROOT / "docs" / "weekly-review" / "final-wbr-review-mode.html"


class ButtonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.stack.append((tag, data))
        if tag == "button":
            ancestors = [entry[1].get("class", "") for entry in self.stack[:-1]]
            self.buttons.append((data, ancestors))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


class FinalWbrMockupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = MOCKUP.read_text()
        cls.script = "\n".join(re.findall(r"<script[^>]*>([\s\S]*?)</script>", cls.html))
        cls.parser = ButtonParser()
        cls.parser.feed(cls.html)

    def test_every_static_button_has_an_interaction_route(self):
        missing = []
        for attrs, ancestors in self.parser.buttons:
            button_id = attrs.get("id")
            classes = attrs.get("class", "")
            delegated = (
                "suggestion-actions" in ancestors
                or "queue-tab" in classes
                or "memory-tab" in classes
            )
            if button_id:
                if button_id not in self.script:
                    missing.append(button_id)
            elif not delegated:
                missing.append(attrs.get("aria-label") or classes or "unnamed button")
        self.assertEqual(missing, [])

    def test_static_ids_are_unique(self):
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        self.assertEqual(duplicates, [])

    def test_finalized_review_workflows_remain_visible(self):
        for copy in (
            "one persistent Slack thread",
            "Names mentioned here are resolved to Slack tags",
            "Add Granola meeting",
            "Actions &amp; follow-ups",
            "Already actioned",
            "Self-recovering",
            "Next review date",
            "Add action manually",
            "Finish CE review",
            "CE Memory",
            'data-memory="story"',
            'data-memory="work"',
            'data-memory="sources"',
        ):
            self.assertIn(copy, self.html)

    def test_slack_is_not_duplicated_in_the_bottom_dock(self):
        footer = re.search(r"<footer class=\"footer\">([\s\S]*?)</footer>", self.html).group(1)
        self.assertNotIn("Slack", footer)
        self.assertIn("Add Granola meeting", footer)

    def test_action_and_check_confirmation_require_explicit_fields(self):
        self.assertIn('aria-label="Action owner"', self.html)
        self.assertIn('aria-label="Action due date"', self.html)
        self.assertIn('aria-label="Next review date"', self.html)
        self.assertIn("Confirm an owner for work that needs action", self.script)
        self.assertIn("Choose the next review date", self.script)

    def test_note_slack_review_and_drawers_are_wired(self):
        for route in (
            "BGM note saved",
            "BGM note deleted · audit record retained",
            "CE discussion started · replies will sync automatically",
            "CE review finished · open work will carry forward",
            "open-ce-drawer",
            "open-memory",
            "next-ce",
        ):
            self.assertIn(route, self.script)


if __name__ == "__main__":
    unittest.main()
