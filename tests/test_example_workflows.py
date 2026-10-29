"""The example workflow JSON matches the registered node contracts."""

from __future__ import annotations

import json
import unittest

from _loader import PACKAGE_DIR, load_module

nodes = load_module("nodes")
MAPPINGS = nodes.NODE_CLASS_MAPPINGS
WORKFLOW_DIR = PACKAGE_DIR / "example_workflows"
PRIMITIVES = {"STRING", "INT", "FLOAT", "BOOLEAN"}


def load_workflows():
    for path in sorted(WORKFLOW_DIR.glob("*.json")):
        yield path, json.loads(path.read_text(encoding="utf-8"))


class WorkflowStructureTests(unittest.TestCase):
    def test_example_workflows_exist(self):
        paths = list(WORKFLOW_DIR.glob("*.json"))
        self.assertTrue(paths, "No example workflow JSON files found.")

    def test_node_and_link_integrity(self):
        for path, data in load_workflows():
            with self.subTest(workflow=path.name):
                self.assertEqual(data["version"], 0.4)
                self.assertIn("nodes", data)
                self.assertIn("links", data)

                ids = [node["id"] for node in data["nodes"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(data["last_node_id"], max(ids))

                links = {link[0]: link for link in data["links"]}
                self.assertEqual(len(links), len(data["links"]))
                self.assertEqual(
                    data["last_link_id"], max(links, default=0)
                )

                by_id = {node["id"]: node for node in data["nodes"]}
                for link_id, link in links.items():
                    _, from_id, from_slot, to_id, to_slot, link_type = link
                    self.assertIn(from_id, by_id)
                    self.assertIn(to_id, by_id)
                    source = by_id[from_id]
                    target = by_id[to_id]

                    self.assertLess(from_slot, len(source["outputs"]))
                    self.assertLess(to_slot, len(target["inputs"]))
                    self.assertEqual(
                        source["outputs"][from_slot]["type"], link_type
                    )
                    self.assertEqual(
                        target["inputs"][to_slot]["type"], link_type
                    )
                    self.assertEqual(
                        target["inputs"][to_slot]["link"], link_id
                    )
                    self.assertIn(
                        link_id, source["outputs"][from_slot]["links"]
                    )

                for node in data["nodes"]:
                    for slot, entry in enumerate(node["inputs"]):
                        link_id = entry.get("link")
                        if link_id is None:
                            continue
                        self.assertIn(link_id, links)
                        link = links[link_id]
                        self.assertEqual(link[3], node["id"])
                        self.assertEqual(link[4], slot)

    def test_node_inputs_and_widgets_match_input_types(self):
        for path, data in load_workflows():
            for node in data["nodes"]:
                with self.subTest(workflow=path.name, node=node["id"]):
                    if node["type"] == "MarkdownNote":
                        self.assertEqual(node["inputs"], [])
                        self.assertEqual(node["outputs"], [])
                        self.assertEqual(len(node["widgets_values"]), 1)
                        continue

                    self.assertIn(node["type"], MAPPINGS)
                    cls = MAPPINGS[node["type"]]
                    spec = cls.INPUT_TYPES()

                    expected = []
                    for section in ("required", "optional"):
                        for name, definition in spec.get(section, {}).items():
                            raw_type = definition[0]
                            expected.append({
                                "name": name,
                                "type": (
                                    "COMBO"
                                    if isinstance(raw_type, list)
                                    else raw_type
                                ),
                                "widget": (
                                    isinstance(raw_type, list)
                                    or raw_type in PRIMITIVES
                                ),
                                "definition": definition,
                            })

                    self.assertEqual(len(node["inputs"]), len(expected))
                    widget_values = node["widgets_values"]
                    widget_index = 0
                    for entry, spec_entry in zip(node["inputs"], expected):
                        self.assertEqual(entry["name"], spec_entry["name"])
                        self.assertEqual(entry["type"], spec_entry["type"])
                        self.assertEqual(
                            "widget" in entry, spec_entry["widget"]
                        )

                        if not spec_entry["widget"]:
                            self.assertNotIn("widget", entry)
                            continue

                        self.assertEqual(
                            entry["widget"], {"name": spec_entry["name"]}
                        )
                        self.assertLess(widget_index, len(widget_values))
                        value = widget_values[widget_index]
                        widget_index += 1
                        self.assert_widget_value(
                            spec_entry["definition"], value
                        )

                    self.assertEqual(widget_index, len(widget_values))

                    self.assertEqual(
                        len(node["outputs"]), len(cls.RETURN_TYPES)
                    )
                    for output, name, output_type in zip(
                        node["outputs"], cls.RETURN_NAMES, cls.RETURN_TYPES
                    ):
                        self.assertEqual(output["name"], name)
                        self.assertEqual(output["type"], output_type)

                    self.assertEqual(
                        node["properties"].get("Node name for S&R"),
                        node["type"],
                    )

    def assert_widget_value(self, definition, value):
        raw_type, options = definition[0], definition[1]
        if isinstance(raw_type, list):
            self.assertIn(value, raw_type)
            return
        if raw_type == "STRING":
            self.assertIsInstance(value, str)
        elif raw_type == "BOOLEAN":
            self.assertIsInstance(value, bool)
        elif raw_type == "INT":
            self.assertIsInstance(value, int)
            self.assertNotIsInstance(value, bool)
            self.assertGreaterEqual(value, options["min"])
            self.assertLessEqual(value, options["max"])
        elif raw_type == "FLOAT":
            self.assertIsInstance(value, (int, float))
            self.assertNotIsInstance(value, bool)
            self.assertGreaterEqual(value, options["min"])
            self.assertLessEqual(value, options["max"])
        else:
            self.fail(f"Unexpected widget type {raw_type}")


if __name__ == "__main__":
    unittest.main()
