#!/usr/bin/env python

"""Tests for the Tkinter GUI's non-visual option and profile models."""

import argparse
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testutils import bootstrap
bootstrap()

from lib.gui.models import OptionCatalog
from lib.gui.models import OptionModel
from lib.gui.models import ProfileStore


class TestGuiOptionModel(unittest.TestCase):
    def setUp(self):
        parser = argparse.ArgumentParser()
        target = parser.add_argument_group("Target", "target options")
        target.add_argument("-u", "--url", dest="url")
        target.add_argument("--level", dest="level", type=int, default=1)
        target.add_argument("--batch", dest="batch", action="store_true")
        self.catalog = OptionCatalog(parser)
        self.model = OptionModel(self.catalog)

    def test_catalog_includes_root_and_grouped_options(self):
        self.assertIsNotNone(self.catalog.get("url"))
        self.assertIsNotNone(self.catalog.get("level"))
        self.assertIsNotNone(self.catalog.get("batch"))
        self.assertEqual(self.catalog.get("level").kind, "int")

    def test_apply_converts_values_and_builds_config(self):
        self.model.apply({"url": "http://example.test/?id=1", "level": "3", "batch": True})
        self.assertEqual(self.model.get("level"), 3)
        self.assertEqual(self.model.get("url"), "http://example.test/?id=1")
        self.assertTrue(self.model.get("batch"))
        self.assertFalse(self.model.changed)
        self.assertEqual(self.model.collect_config()["level"], 3)

    def test_search_matches_flags_and_help(self):
        matches = self.catalog.search("url")
        self.assertEqual(matches[0].dest, "url")


class TestGuiProfileStore(unittest.TestCase):
    def test_custom_profiles_round_trip(self):
        directory = tempfile.mkdtemp()
        filename = os.path.join(directory, "profiles.json")
        try:
            store = ProfileStore(filename)
            self.assertTrue(store.save("Local audit", {"level": 2, "batch": True}))
            loaded = ProfileStore(filename)
            self.assertEqual(loaded.values("Local audit")["level"], 2)
            self.assertTrue(loaded.delete("Local audit"))
            self.assertNotIn("Local audit", loaded.names())
        finally:
            try:
                os.remove(filename)
            except OSError:
                pass
            try:
                os.rmdir(directory)
            except OSError:
                pass

    def test_built_ins_cannot_be_overwritten(self):
        directory = tempfile.mkdtemp()
        try:
            store = ProfileStore(os.path.join(directory, "profiles.json"))
            self.assertFalse(store.save("Detection only", {"level": 6}))
        finally:
            try:
                os.rmdir(directory)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
