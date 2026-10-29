"""Widget-value sanitizers."""

from __future__ import annotations

import unittest

from _loader import load_module

sanitize = load_module("sanitize")


class CleanTextTests(unittest.TestCase):
    def test_strips_text(self):
        self.assertEqual(sanitize.clean_text("  hello  "), "hello")

    def test_ignores_shifted_boolean_artifacts(self):
        for value in ("", "   ", "True", "FALSE", "none", "null", "undefined"):
            self.assertEqual(sanitize.clean_text(value), "")
        for value in (None, True, 3, ["x"]):
            self.assertEqual(sanitize.clean_text(value, "fallback"), "fallback")


class NumberTests(unittest.TestCase):
    def test_parses_numbers_and_clamps(self):
        self.assertEqual(sanitize.coerce_int("16000", 8000, 1000, 48000), 16000)
        self.assertEqual(sanitize.coerce_int("nope", 8000, 1000, 48000), 8000)
        self.assertEqual(sanitize.coerce_int(True, 8000), 8000)
        self.assertEqual(sanitize.coerce_int(999999, 8000, 1000, 48000), 48000)
        self.assertEqual(sanitize.coerce_float("-35.5", -30.0, -80.0, 0.0), -35.5)
        self.assertEqual(sanitize.coerce_float(None, -30.0), -30.0)


class BoolTests(unittest.TestCase):
    def test_parses_booleans(self):
        self.assertTrue(sanitize.coerce_bool("true"))
        self.assertTrue(sanitize.coerce_bool("1"))
        self.assertTrue(sanitize.coerce_bool(1))
        self.assertFalse(sanitize.coerce_bool("false"))
        self.assertFalse(sanitize.coerce_bool("0"))
        self.assertEqual(sanitize.coerce_bool("garbage", True), True)
        self.assertEqual(sanitize.coerce_bool("garbage", False), False)


class ChoiceTests(unittest.TestCase):
    def test_choice_is_case_insensitive(self):
        choices = ("file", "url")
        self.assertEqual(sanitize.coerce_choice("URL", choices, "file"), "url")
        self.assertEqual(sanitize.coerce_choice("bogus", choices, "file"), "file")

    def test_encoding_falls_back_for_unknown_codec(self):
        self.assertEqual(
            sanitize.coerce_encoding("latin-1", ("utf-8", "gbk"), "utf-8"),
            "utf-8",
        )
        self.assertEqual(
            sanitize.coerce_encoding("gbk", ("utf-8", "gbk"), "utf-8"), "gbk"
        )


if __name__ == "__main__":
    unittest.main()
