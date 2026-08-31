# sqlmap

[![.github/workflows/tests.yml](https://github.com/sqlmapproject/sqlmap/actions/workflows/tests.yml/badge.svg)](https://github.com/sqlmapproject/sqlmap/actions/workflows/tests.yml) [![Python 2.7|3.x](https://img.shields.io/badge/python-2.7|3.x-yellow.svg)](https://www.python.org/) [![License](https://img.shields.io/badge/license-GPLv2-red.svg)](https://raw.githubusercontent.com/sqlmapproject/sqlmap/master/LICENSE) [![x](https://img.shields.io/badge/x-@sqlmap-blue.svg)](https://x.com/sqlmap)

## Changelog

### 2026-08-30 — Poattys Edition GUI update

This release adds a modular, Zenmap-inspired Tkinter desktop interface while preserving the existing sqlmap engine and command-line workflow.

- Added the `python sqlmap.py --gui` entry point with lazy Tkinter loading, so CLI and API workflows remain usable on headless systems.
- Added dedicated **Scan**, **Options**, **Results**, and **Output** views with command preview and parser-backed option discovery.
- Added URL, HTTP request file, Burp/WebScarab log, HAR, OpenAPI/Swagger, target-list, and direct database target workflows.
- Added asynchronous process execution, incremental console output, interactive prompt input, cancellation, and process-group termination.
- Added built-in and persistent custom profiles, configuration import/export, report export, and console-output export.
- Added structured result rendering from `--report-json`, high-impact option confirmations, and profile protection for secret fields.
- Refactored the former GUI module into a compatibility adapter and added automated model/runner coverage.

sqlmap is an open source penetration testing tool that automates the process of detecting and exploiting SQL injection flaws and taking over of database servers. It comes with a powerful detection engine, many niche features for the ultimate penetration tester, and a broad range of switches including database fingerprinting, over data fetching from the database, accessing the underlying file system, and executing commands on the operating system via out-of-band connections.

Screenshots
----

![Screenshot](https://raw.github.com/wiki/sqlmapproject/sqlmap/images/sqlmap_screenshot.png)

You can visit the [collection of screenshots](https://github.com/sqlmapproject/sqlmap/wiki/Screenshots) demonstrating some of the features on the wiki.

Installation
----

You can download the latest tarball by clicking [here](https://github.com/sqlmapproject/sqlmap/tarball/master) or latest zipball by clicking [here](https://github.com/sqlmapproject/sqlmap/zipball/master).

Preferably, you can download sqlmap by cloning the [Git](https://github.com/sqlmapproject/sqlmap) repository:

    git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git sqlmap-dev

sqlmap works out of the box with [Python](https://www.python.org/download/) version **2.7** and **3.x** on any platform.

Usage
----

To get a list of basic options and switches use:

    python sqlmap.py -h

To get a list of all options and switches use:

    python sqlmap.py -hh

You can find a sample run [here](https://asciinema.org/a/46601).
To get an overview of sqlmap capabilities, a list of supported features, and a description of all options and switches, along with examples, you are advised to consult the [user's manual](https://github.com/sqlmapproject/sqlmap/wiki/Usage).

Graphical interface
----

The Poattys Edition includes a Zenmap-inspired Tkinter front-end for operators who prefer a guided visual workflow. The GUI is a presentation and orchestration layer: sqlmap remains the scan engine, and the command-line interface remains available for automation and headless environments.

Launch the interface from the repository root:

    python sqlmap.py --gui

### GUI workflow

1. **Define the target** in the Scan tab. You can use a URL, direct database connection, HTTP request file, Burp/WebScarab log, HAR export, OpenAPI/Swagger document, or target list.
2. **Choose a profile** or configure the scan manually. The built-in profiles are `Detection only`, `Standard audit`, and `Database inventory`; custom profiles can be saved for reuse.
3. **Review the generated command** before execution. Common controls are available on the Scan tab, while the Options tab exposes public sqlmap options grouped by parser category and searchable by name, flag, or description.
4. **Run and monitor the process** from the Output tab. Output is streamed incrementally, interactive prompts can be answered through the input field, and a running process can be stopped from the toolbar or with `Esc`.
5. **Inspect and export results** in the Results tab. The GUI reads sqlmap's structured `--report-json` output and can save the report as JSON or save the complete console output as a log.

### Configuration and profiles

- Import and export sqlmap INI configuration files from the **File** menu or the Scan tab.
- Save custom profiles in the **Profile** menu. Profiles are stored in `gui-profiles.json` under the sqlmap home directory.
- Secret fields, including cookies, credentials, and authentication headers, are excluded from custom profile files. Use explicit configuration export when a secret must be included in a run configuration.
- The GUI normalizes repeated `-H/--header` values when exporting configuration files so headers are not silently discarded.

### Safety and operations

Use the GUI only for targets and requests you are authorized to test. High-impact capabilities are identified in the advanced options and require explicit confirmation before execution. Review the target source, generated command, scope, and selected profile before starting a run.

The GUI uses an isolated child process and does not reimplement the scanner. Stop requests terminate the process cleanly first and use process-group termination if the process does not exit. Report files are temporary unless explicitly exported by the operator.

### Dependencies and headless environments

Tkinter must be available in the Python installation. On Debian or Ubuntu, install the package commonly named `python3-tk`; Windows Python installers commonly include Tk support. To verify the dependency without running a scan, use:

    python -c "import tkinter; print('Tkinter available')"

A headless environment continues to support the command-line and API workflows, but cannot open the desktop GUI. No GUI dependency is imported until `--gui` is requested.

Links
----

* Homepage: https://sqlmap.org
* Download: [.tar.gz](https://github.com/sqlmapproject/sqlmap/tarball/master) or [.zip](https://github.com/sqlmapproject/sqlmap/zipball/master)
* Commits RSS feed: https://github.com/sqlmapproject/sqlmap/commits/master.atom
* Issue tracker: https://github.com/sqlmapproject/sqlmap/issues
* User's manual: https://github.com/sqlmapproject/sqlmap/wiki
* Frequently Asked Questions (FAQ): https://github.com/sqlmapproject/sqlmap/wiki/FAQ
* X: [@sqlmap](https://x.com/sqlmap)
* Demos: [https://www.youtube.com/user/inquisb/videos](https://www.youtube.com/user/inquisb/videos)
* Playground: https://sekumart.sekuripy.hr
* Research: https://www.sekuripy.hr/labs/sqlmap/#research
* Screenshots: https://github.com/sqlmapproject/sqlmap/wiki/Screenshots

Translations
----

* [Arabic](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-ar-AR.md)
* [Bengali](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-bn-BD.md)
* [Bulgarian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-bg-BG.md)
* [Chinese](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-zh-CN.md)
* [Croatian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-hr-HR.md)
* [Dutch](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-nl-NL.md)
* [French](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-fr-FR.md)
* [Georgian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-ka-GE.md)
* [German](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-de-DE.md)
* [Greek](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-gr-GR.md)
* [Hindi](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-in-HI.md)
* [Indonesian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-id-ID.md)
* [Italian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-it-IT.md)
* [Japanese](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-ja-JP.md)
* [Korean](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-ko-KR.md)
* [Kurdish (Central)](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-ckb-KU.md)
* [Persian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-fa-IR.md)
* [Polish](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-pl-PL.md)
* [Portuguese](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-pt-BR.md)
* [Russian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-ru-RU.md)
* [Serbian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-rs-RS.md)
* [Slovak](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-sk-SK.md)
* [Spanish](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-es-MX.md)
* [Turkish](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-tr-TR.md)
* [Ukrainian](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-uk-UA.md)
* [Vietnamese](https://github.com/sqlmapproject/sqlmap/blob/master/doc/translations/README-vi-VN.md)
