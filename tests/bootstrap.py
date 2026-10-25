"""The retired old-host bootstrap command stays removed."""
from pathlib import Path
import unittest


class BootstrapTests(unittest.TestCase):
    def test_retired_bootstrap_is_removed(self):
        script = Path(__file__).resolve().parents[1] / "deploy/bootstrap-accountcontext.py"
        self.assertFalse(script.exists())


if __name__ == "__main__":
    unittest.main()
