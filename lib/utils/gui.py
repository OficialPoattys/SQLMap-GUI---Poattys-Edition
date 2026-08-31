#!/usr/bin/env python

"""Backward-compatible entry point for the sqlmap Tkinter GUI.

The implementation lives in ``lib/gui`` so the user interface is separated
from the engine's utility namespace.  These aliases are retained for existing
helper tests and for third-party code that imported the old module.
"""

from __future__ import print_function

import time

from lib.gui.compat import group_description as _groupDescription
from lib.gui.compat import group_options as _groupOptions
from lib.gui.compat import group_title as _groupTitle
from lib.gui.compat import list2cmdline as _list2cmdline
from lib.gui.compat import option_choices as _optChoices
from lib.gui.compat import option_dest as _optDest
from lib.gui.compat import option_help as _optHelp
from lib.gui.compat import option_label as _optionLabel
from lib.gui.compat import option_strings as _optStrings
from lib.gui.compat import option_takes_value as _optTakesValue
from lib.gui.compat import option_value_type as _optValueType
from lib.gui.compat import parser_groups as _parserGroups
from lib.gui.compat import preferred_flag as _preferredFlag
from lib.gui.compat import quote_arg as _quoteArg
from lib.gui.compat import to_bytes as _toBytes
from lib.gui.compat import to_text as _toText
from lib.gui import runGui
from lib.gui.app import SqlmapGui


def _waitForProcess(process, timeout):
    """Python 2 compatible replacement for Popen.wait(timeout=...)."""
    deadline = time.time() + max(0.0, timeout)
    while process.poll() is None and time.time() < deadline:
        time.sleep(0.03)
    return process.poll()


# Names used by the former GUI implementation and by integrations that adopted
# the more verbose ``_option*`` spelling are both kept available.
_optionStrings = _optStrings
_optionDest = _optDest
_optionHelp = _optHelp
_optionChoices = _optChoices
_optionTakesValue = _optTakesValue
_optionValueType = _optValueType


__all__ = [
    "runGui", "_parserGroups", "_groupOptions", "_groupTitle", "_groupDescription",
    "_optStrings", "_optDest", "_optHelp", "_optChoices", "_optTakesValue",
    "_optValueType", "_optionStrings", "_optionDest", "_optionHelp", "_optionChoices",
    "_optionTakesValue", "_optionValueType", "_optionLabel", "_preferredFlag", "_quoteArg",
    "_toText", "_toBytes", "_list2cmdline",
]
