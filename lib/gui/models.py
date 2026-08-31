#!/usr/bin/env python

"""Non-visual models used by the sqlmap desktop interface."""

from __future__ import print_function

import io
import json
import os

from lib.core.data import paths
from lib.core.defaults import defaults
from lib.gui.compat import group_description
from lib.gui.compat import group_title
from lib.gui.compat import option_choices
from lib.gui.compat import option_dest
from lib.gui.compat import option_help
from lib.gui.compat import option_label
from lib.gui.compat import option_strings
from lib.gui.compat import option_takes_value
from lib.gui.compat import option_value_type
from lib.gui.compat import preferred_flag


# The GUI deliberately omits internal switches, while still exposing all normal
# scan options in the Advanced editor.  The runner adds report-json internally.
INTERNAL_OPTIONS = frozenset((
    "advancedHelp", "showVersion", "hashFile", "dummy", "yuge",
    "jitter", "debug", "deprecations", "disableJson", "api", "taskid",
    "database", "reportJson", "configFile", "saveConfig", "sqlShell",
))

SECRET_OPTIONS = frozenset((
    "cookie", "liveCookies", "loadCookies", "authCred", "authFile",
    "proxyCred", "dbmsCred", "oobToken", "oobServer", "header", "headers",
))

DANGEROUS_OPTIONS = frozenset((
    "dumpAll", "dumpTable", "sqlQuery", "sqlFile", "fileWrite", "osCmd",
    "osShell", "osPwn", "osSmb", "osBof", "privEsc", "udfInject",
    "regAdd", "regDel", "dnsDomain", "secondUrl", "secondReq",
))

FILE_OPTIONS = frozenset((
    "requestFile", "logFile", "bulkFile", "sessionFile", "openApiFile",
    "loadCookies", "liveCookies", "safeReqFile", "harFile", "outputDir",
    "dumpFile", "fileWrite", "sqlFile", "msfPath", "shLib",
))


class OptionSpec(object):
    """A stable, UI-facing description of one parser option."""

    def __init__(self, option, section):
        self.option = option
        self.section = section
        self.dest = option_dest(option)
        self.flags = option_strings(option)
        self.label = option_label(option)
        self.flag = preferred_flag(option)
        self.help = option_help(option)
        self.takes_value = option_takes_value(option)
        self.kind = option_value_type(option) if self.takes_value else "bool"
        self.choices = option_choices(option)
        default = defaults.get(self.dest)
        if self.kind == "bool":
            self.default = bool(default)
        else:
            self.default = "" if default in (None, False) else default
        self.secret = self.dest in SECRET_OPTIONS
        self.dangerous = self.dest in DANGEROUS_OPTIONS
        self.file_value = self.dest in FILE_OPTIONS
        self.advanced = section not in ("Target", "Request", "Detection", "Enumeration")

    def is_default(self, value):
        if self.kind == "bool":
            return bool(value) == bool(self.default)
        if value in (None, ""):
            return self.default in (None, "")
        return str(value) == str(self.default)

    def display_default(self):
        if self.kind == "bool":
            return "on" if self.default else "off"
        return str(self.default) if self.default not in (None, "") else "not set"


class OptionCatalog(object):
    """Build option metadata once from the existing sqlmap parser."""

    def __init__(self, parser):
        self.groups = []
        self.by_dest = {}
        self.order = []

        # De-duplicate by destination.  The parser currently has unique
        # destinations, but this makes the GUI robust to future aliases.
        for group, options in self._public_groups(parser):
            section = group_title(group)
            specs = []
            for option in options:
                spec = OptionSpec(option, section)
                if spec.dest in self.by_dest:
                    continue
                self.by_dest[spec.dest] = spec
                self.order.append(spec.dest)
                specs.append(spec)
            if specs:
                self.groups.append((section, group_description(group), specs))

    def _public_groups(self, parser):
        from lib.gui.compat import public_option_groups
        for group, options in public_option_groups(parser):
            filtered = [option for option in options if option_dest(option) not in INTERNAL_OPTIONS]
            if filtered:
                yield group, filtered

    def get(self, dest):
        return self.by_dest.get(dest)

    def defaults(self):
        return dict((dest, spec.default) for dest, spec in self.by_dest.items())

    def user_values(self, values):
        return dict((dest, values.get(dest, spec.default)) for dest, spec in self.by_dest.items())

    def search(self, query):
        query = (query or "").strip().lower()
        if not query:
            return list(self.by_dest.values())
        tokens = query.split()
        scored = []
        for index, dest in enumerate(self.order):
            spec = self.by_dest[dest]
            haystack = " ".join((dest, spec.label, spec.section, spec.help)).lower()
            if not all(token in haystack for token in tokens):
                continue
            score = 0
            if dest.lower().startswith(query):
                score -= 30
            if spec.flag.lower().startswith(query) or spec.flag.lower().startswith("--" + query):
                score -= 20
            if spec.section.lower().startswith(query):
                score -= 10
            scored.append((score, index, spec))
        scored.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in scored]


class OptionModel(object):
    """Typed option values shared by every visual surface."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.values = catalog.defaults()
        self.changed = False

    def reset(self):
        self.values = self.catalog.defaults()
        self.changed = False

    def get(self, dest):
        spec = self.catalog.get(dest)
        return self.values.get(dest, spec.default if spec else None)

    def set(self, dest, value):
        if dest not in self.catalog.by_dest:
            return
        self.values[dest] = value
        self.changed = True

    def snapshot(self, include_secrets=True):
        result = {}
        for dest in self.catalog.order:
            spec = self.catalog.by_dest[dest]
            if include_secrets or not spec.secret:
                result[dest] = self.values.get(dest, spec.default)
        return result

    def apply(self, values):
        if not isinstance(values, dict):
            return
        for dest, spec in self.catalog.by_dest.items():
            if dest not in values:
                continue
            value = values[dest]
            try:
                if spec.kind == "bool":
                    value = bool(value)
                elif spec.kind == "int":
                    value = "" if value in (None, "") else int(value)
                elif spec.kind == "float":
                    value = "" if value in (None, "") else float(value)
                elif value is None:
                    value = ""
            except (TypeError, ValueError):
                continue
            self.values[dest] = value
        self.changed = False

    def collect_config(self):
        """Return values suitable for sqlmap's saveConfig()."""
        result = {}
        for dest, spec in self.catalog.by_dest.items():
            value = self.values.get(dest, spec.default)
            if spec.kind == "bool":
                result[dest] = bool(value)
            elif value in (None, ""):
                result[dest] = None
            elif spec.kind == "int":
                try:
                    result[dest] = int(value)
                except (TypeError, ValueError):
                    result[dest] = None
            elif spec.kind == "float":
                try:
                    result[dest] = float(value)
                except (TypeError, ValueError):
                    result[dest] = None
            else:
                result[dest] = value
        return result


class ProfileStore(object):
    """Persists GUI profiles without touching sqlmap's engine/session files."""

    BUILT_INS = {
        "Detection only": {
            "level": 1, "risk": 1, "technique": "BEUSTQ",
        },
        "Standard audit": {
            "level": 2, "risk": 1, "technique": "BEUSTQ",
            "getBanner": True, "getCurrentUser": True, "getCurrentDb": True,
        },
        "Database inventory": {
            "level": 2, "risk": 1, "technique": "BEU",
            "getBanner": True, "getCurrentUser": True, "getCurrentDb": True,
            "getDbs": True, "getTables": True,
        },
    }

    def __init__(self, filename=None):
        if filename:
            self.filename = filename
        else:
            home = paths.get("SQLMAP_HOME_PATH")
            if not home:
                home = os.path.join(os.path.expanduser("~"), ".sqlmap")
            self.filename = os.path.join(home, "gui-profiles.json")
        self.custom = {}
        self.load()

    def names(self):
        return list(self.BUILT_INS.keys()) + sorted(self.custom.keys())

    def values(self, name):
        if name in self.BUILT_INS:
            return dict(self.BUILT_INS[name])
        return dict(self.custom.get(name, {}))

    def save(self, name, values):
        if not name or name in self.BUILT_INS:
            return False
        self.custom[name] = dict(values)
        self._write()
        return True

    def delete(self, name):
        if name in self.custom:
            del self.custom[name]
            self._write()
            return True
        return False

    def load(self):
        self.custom = {}
        try:
            with io.open(self.filename, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
                for name, values in data["profiles"].items():
                    if isinstance(name, str) and isinstance(values, dict) and name not in self.BUILT_INS:
                        self.custom[name] = values
        except (IOError, OSError, ValueError, TypeError):
            pass

    def _write(self):
        directory = os.path.dirname(self.filename) or "."
        temp = self.filename + ".tmp"
        try:
            if not os.path.isdir(directory):
                os.makedirs(directory)
            with io.open(temp, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "profiles": self.custom}, handle, indent=2, sort_keys=True)
            try:
                os.remove(self.filename)
            except OSError:
                pass
            os.rename(temp, self.filename)
        except (IOError, OSError, TypeError, ValueError):
            try:
                os.remove(temp)
            except (IOError, OSError):
                pass


def profile_description(name):
    descriptions = {
        "Detection only": "Confirms injection points without requesting database contents.",
        "Standard audit": "Detection plus basic DBMS and account fingerprinting.",
        "Database inventory": "Lists databases and tables. Review the target scope first.",
    }
    return descriptions.get(name, "User-defined profile")


__all__ = [
    "OptionSpec", "OptionCatalog", "OptionModel", "ProfileStore",
    "INTERNAL_OPTIONS", "SECRET_OPTIONS", "DANGEROUS_OPTIONS", "FILE_OPTIONS",
    "profile_description",
]
