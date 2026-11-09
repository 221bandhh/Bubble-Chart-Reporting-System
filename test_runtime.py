import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime import working_directory


class RuntimePathTests(unittest.TestCase):
    def test_packaged_application_uses_user_data_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("sys.frozen", True, create=True), patch.dict("os.environ", {"LOCALAPPDATA": folder}):
                self.assertEqual(working_directory(), Path(folder) / "BubbleInspection")

    def test_explicit_workspace_is_respected(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(working_directory(folder), Path(folder).resolve())


if __name__ == "__main__":
    unittest.main()
