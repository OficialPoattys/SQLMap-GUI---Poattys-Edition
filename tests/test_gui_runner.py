#!/usr/bin/env python

"""Tests for the GUI subprocess runner without launching sqlmap scans."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _testutils import bootstrap
bootstrap()

from lib.gui.runner import ScanRunner


class TestScanRunner(unittest.TestCase):
    def test_incremental_output_and_stdin(self):
        runner = ScanRunner(os.getcwd())
        code = (
            "import sys; "
            "print('ready', flush=True); "
            "answer = sys.stdin.readline().strip(); "
            "print('received:' + answer, flush=True)"
        )
        runner.start([sys.executable, "-c", code])
        events = []
        deadline = time.time() + 5
        sent = False
        while time.time() < deadline and (runner.is_running() or not runner.events.empty()):
            for event in runner.drain():
                events.append(event)
                if event[0] == "output" and "ready" in event[1] and not sent:
                    sent = runner.send_input("gui-answer")
            if not runner.is_running() and runner.events.empty():
                break
            time.sleep(0.01)

        output = "".join(event[1] for event in events if event[0] == "output")
        finished = [event for event in events if event[0] == "finished"]
        self.assertTrue(sent)
        self.assertIn("ready", output)
        self.assertIn("received:gui-answer", output)
        self.assertEqual(finished[-1][1], 0)

    def test_stop_terminates_process(self):
        runner = ScanRunner(os.getcwd())
        runner.start([sys.executable, "-c", "import time; time.sleep(10)"])
        runner.stop(force=True)
        deadline = time.time() + 5
        while time.time() < deadline and runner.is_running():
            time.sleep(0.02)
        self.assertFalse(runner.is_running())


if __name__ == "__main__":
    unittest.main()
