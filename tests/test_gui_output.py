#!/usr/bin/env python

"""Tests for GUI output color classification."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testutils import bootstrap
bootstrap()

from lib.gui.app import SqlmapGui


class TestGuiOutputColorTags(unittest.TestCase):
    def setUp(self):
        self.gui = SqlmapGui.__new__(SqlmapGui)

    def test_log_levels_map_to_terminal_tags(self):
        self.assertEqual(self.gui._output_tag("[INFO] request sent"), "info")
        self.assertEqual(self.gui._output_tag("[WARNING] blocked"), "warning")
        self.assertEqual(self.gui._output_tag("[CRITICAL] failed"), "critical")
        self.assertEqual(self.gui._output_tag("[DEBUG] details"), "debug")
        self.assertEqual(self.gui._output_tag("[PAYLOAD] value"), "payload")

    def test_ansi_colors_are_classified_without_leaking_codes(self):
        self.assertEqual(self.gui._output_tag("\033[32mplain info\033[0m"), "info")
        self.assertEqual(self.gui._output_tag("\033[31mplain error\033[0m"), "error")

    def test_banner_has_its_own_tag(self):
        value = "        ___\n       __H__\n       https://sqlmap.org\n"
        self.assertEqual(self.gui._output_tag(value), "banner")


if __name__ == "__main__":
    unittest.main()
