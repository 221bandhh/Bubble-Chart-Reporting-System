"""Compatibility entry point and public API for the report generator."""

import os
import sys

from report_system.core.engine import *  # noqa: F401,F403
from report_system.ui.app import ReportGeneratorApp, run


if __name__ == "__main__":
    source = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    run(source)

