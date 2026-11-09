"""Compatibility entry point for the product bubble editor."""

import os
import sys

from ui.bubble_app import run
from core.runtime import working_directory


if __name__ == "__main__":
    workspace = working_directory(sys.argv[1] if len(sys.argv) > 1 else None)
    run(workspace)

