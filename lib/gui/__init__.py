#!/usr/bin/env python

"""Tkinter front-end for sqlmap.

The package is intentionally UI-agnostic at import time.  Tkinter is loaded only
when :func:`runGui` is called so the command line engine, unit tests, and API do
not acquire a desktop dependency.
"""

from __future__ import print_function

from lib.core.common import getSafeExString
from lib.core.exception import SqlmapMissingDependence


def runGui(parser):
    """Start the desktop interface using the parser built by sqlmap."""

    try:
        from thirdparty.six.moves import tkinter as _tkinter
        from thirdparty.six.moves import tkinter_scrolledtext as _scrolledtext
        from thirdparty.six.moves import tkinter_ttk as _ttk
        from thirdparty.six.moves import tkinter_messagebox as _messagebox
        from thirdparty.six.moves import tkinter_filedialog as _filedialog
        from thirdparty.six.moves import tkinter_font as _font
        from thirdparty.six.moves import tkinter_simpledialog as _simpledialog
    except ImportError as ex:
        raise SqlmapMissingDependence(
            "missing dependence ('%s'). Install a Python build with Tk support" % getSafeExString(ex)
        )

    from lib.gui.app import SqlmapGui

    app = SqlmapGui(parser, _tkinter, _ttk, _scrolledtext, _messagebox, _filedialog, _font, _simpledialog)
    app.window.mainloop()


__all__ = ["runGui"]
