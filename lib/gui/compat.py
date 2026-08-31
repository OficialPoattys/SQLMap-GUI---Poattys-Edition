#!/usr/bin/env python

"""Small compatibility helpers shared by the Tkinter front-end and tests.

sqlmap still supports optparse on older Python versions and argparse on newer
ones.  The GUI consumes metadata from either parser without importing Tk.
"""

from __future__ import print_function

import subprocess
import sys

try:
    _text_type = unicode
except NameError:
    _text_type = str

_binary_type = str if sys.version_info[0] < 3 else bytes


def to_text(value):
    if value is None:
        return u""
    if isinstance(value, _text_type):
        return value
    if isinstance(value, _binary_type):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return _text_type(value)
    try:
        return _text_type(value)
    except Exception:
        return _text_type(repr(value))


def to_bytes(value):
    if isinstance(value, _binary_type):
        return value
    return to_text(value).encode("utf-8", "replace")


def list2cmdline(arguments):
    values = [to_text(_) for _ in arguments]
    if sys.version_info[0] < 3:
        return to_text(subprocess.list2cmdline([to_bytes(_) for _ in values]))
    return to_text(subprocess.list2cmdline(values))


def quote_arg(value, is_windows=False):
    value = to_text(value)
    if is_windows:
        return list2cmdline([value])
    if not value:
        return u"''"
    safe = u"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-"
    if all(character in safe for character in value):
        return value
    return u"'" + value.replace(u"'", u"'\"'\"'") + u"'"


def parser_groups(parser):
    """Return user-facing option groups for optparse or argparse."""

    groups = getattr(parser, "option_groups", None)
    if groups is None:
        groups = [
            group for group in getattr(parser, "_action_groups", [])
            if getattr(group, "title", None) not in (
                None, "positional arguments", "optional arguments", "options"
            )
        ]
    return groups or []


def group_options(group):
    for attr in ("option_list", "_group_actions", "_actions"):
        if hasattr(group, attr):
            return getattr(group, attr)
    return []


def group_title(group):
    return getattr(group, "title", "") or ""


def group_description(group):
    if hasattr(group, "get_description"):
        try:
            return group.get_description() or ""
        except (AttributeError, TypeError):
            pass
    return getattr(group, "description", "") or ""


def option_strings(option):
    if hasattr(option, "option_strings"):
        return list(option.option_strings)
    return list(getattr(option, "_short_opts", None) or []) + list(getattr(option, "_long_opts", None) or [])


def option_dest(option):
    return getattr(option, "dest", None)


def option_help(option):
    return getattr(option, "help", "") or ""


def option_choices(option):
    choices = getattr(option, "choices", None)
    return list(choices) if choices is not None else None


def option_takes_value(option):
    if hasattr(option, "takes_value"):
        try:
            return option.takes_value()
        except Exception:
            pass
    return getattr(option, "nargs", 1) != 0


def option_value_type(option):
    kind = getattr(option, "type", None)
    if kind in ("int", int):
        return "int"
    if kind in ("float", float):
        return "float"
    return "string"


def option_label(option):
    return ", ".join(option_strings(option)) or (option_dest(option) or "")


def preferred_flag(option):
    strings = option_strings(option)
    long_options = [value for value in strings if value.startswith("--")]
    return (long_options or strings or [""])[0]


# Names that represent program modes rather than sqlmap scan configuration.
UI_ONLY_OPTIONS = frozenset(("gui", "tui", "shell", "configFile"))


class _RootOptionGroup(object):
    """Adapter giving parser-level options the same metadata as a group."""

    title = "General"
    description = ""

    def __init__(self, options):
        self.option_list = options


def public_option_groups(parser):
    """Normalize parser metadata into serializable GUI option specifications."""

    def visible(options):
        result = []
        for option in options:
            dest = option_dest(option)
            if not dest or dest in UI_ONLY_OPTIONS:
                continue
            # optparse uses the literal string SUPPRESSHELP for hidden options.
            help_text = option_help(option)
            if help_text in ("SUPPRESSHELP", "==SUPPRESS=="):
                continue
            result.append(option)
        return result

    result = []
    root = visible(group_options(parser))
    if root:
        # sqlmap places a few global switches (notably -v) directly on the
        # parser instead of in an option group. Treat them as a normal group so
        # the GUI does not silently omit public command-line controls.
        result.append((_RootOptionGroup(root), root))

    for group in parser_groups(parser):
        options = visible(group_options(group))
        if options:
            result.append((group, options))
    return result


__all__ = [
    "to_text", "to_bytes", "list2cmdline", "quote_arg",
    "parser_groups", "group_options", "group_title", "group_description",
    "option_strings", "option_dest", "option_help", "option_choices",
    "option_takes_value", "option_value_type", "option_label", "preferred_flag",
    "public_option_groups", "UI_ONLY_OPTIONS",
]
