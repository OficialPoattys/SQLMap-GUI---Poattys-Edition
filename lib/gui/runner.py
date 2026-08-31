#!/usr/bin/env python

"""Asynchronous local process runner used by the Tkinter front-end."""

from __future__ import print_function

import os
import signal
import subprocess
import sys
import threading
import tempfile

from thirdparty.six.moves import queue as _queue

from lib.gui.compat import to_bytes
from lib.gui.compat import to_text


class ScanRunner(object):
    """Run one sqlmap process without blocking Tk's event loop.

    The runner knows nothing about widgets.  It emits small tuples through a
    queue, which the GUI consumes from its normal ``after`` callback.  This
    makes the lifecycle straightforward to test and keeps subprocess handling
    out of the presentation layer.
    """

    def __init__(self, root_path):
        self.root_path = root_path
        self.process = None
        self.events = _queue.Queue()
        self.report_path = None
        self.command = []
        self._reader = None
        self._stopping = False

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, arguments, report_path=None):
        if self.is_running():
            raise RuntimeError("a scan is already running")

        self.report_path = report_path
        self.command = list(arguments)
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        kwargs = {
            "shell": False,
            "cwd": self.root_path,
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "bufsize": 0,
            "close_fds": os.name != "nt",
            "env": env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        elif sys.version_info >= (3, 2):
            kwargs["start_new_session"] = True
        elif hasattr(os, "setsid"):
            kwargs["preexec_fn"] = os.setsid

        try:
            self.process = subprocess.Popen(self.command, **kwargs)
        except Exception:
            self.process = None
            raise

        self._stopping = False
        self._reader = threading.Thread(target=self._read_output, args=(self.process,))
        self._reader.daemon = True
        self._reader.start()
        self.events.put(("started", self.command))
        return self.process

    def _read_output(self, process):
        try:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                self.events.put(("output", to_text(line)))
        except Exception as ex:
            self.events.put(("error", "console reader error: %s\n" % to_text(ex)))
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass
            try:
                process.stdin.close()
            except Exception:
                pass
            code = process.wait()
            self.events.put(("finished", code, self.report_path))

    def send_input(self, value):
        if not self.is_running() or self.process.stdin is None:
            return False
        try:
            self.process.stdin.write(to_bytes(to_text(value) + u"\n"))
            self.process.stdin.flush()
            return True
        except (IOError, OSError, ValueError):
            return False

    def stop(self, force=False):
        process = self.process
        if process is None or process.poll() is not None:
            return
        self._stopping = True
        try:
            if force:
                self._kill_process_tree(process)
            elif os.name == "nt":
                process.terminate()
            else:
                process.terminate()
        except (OSError, ValueError):
            pass

    def _kill_process_tree(self, process):
        try:
            if os.name != "nt" and hasattr(os, "killpg"):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
        except (OSError, AttributeError, ValueError):
            try:
                process.kill()
            except (OSError, AttributeError, ValueError):
                pass

    def close_stdin(self):
        if self.process is not None and self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except (IOError, OSError, ValueError):
                pass

    def drain(self, limit=256):
        result = []
        for _ in range(limit):
            try:
                result.append(self.events.get_nowait())
            except _queue.Empty:
                break
        return result


def create_report_file():
    handle, path = tempfile.mkstemp(prefix="sqlmap-gui-", suffix=".json")
    os.close(handle)
    return path


__all__ = ["ScanRunner", "create_report_file"]
