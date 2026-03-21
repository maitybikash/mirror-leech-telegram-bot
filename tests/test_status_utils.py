import unittest
from unittest.mock import MagicMock
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Create mocks for dependencies
sys.modules['psutil'] = MagicMock()
sys.modules['bot'] = MagicMock()
sys.modules['bot.core'] = MagicMock()
sys.modules['bot.core.config_manager'] = MagicMock()
sys.modules['bot.helper'] = MagicMock()
sys.modules['bot.helper.telegram_helper'] = MagicMock()
sys.modules['bot.helper.telegram_helper.button_build'] = MagicMock()
sys.modules['bot.helper.telegram_helper.bot_commands'] = MagicMock()

# Now we can import the function to test
import importlib.util

def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    # To handle relative imports like 'from ... import task_dict' in bot/helper/ext_utils/status_utils.py
    # we need to make sure the package structure is partially mocked/represented.
    spec.loader.exec_module(module)
    return module

# Mocking more to avoid errors during exec_module
sys.modules['bot.core.config_manager'].Config = MagicMock()
sys.modules['bot.helper.telegram_helper.button_build'].ButtonMaker = MagicMock()
sys.modules['bot.helper.telegram_helper.bot_commands'].BotCommands = MagicMock()

# Manually load the module
status_utils = import_from_path('bot.helper.ext_utils.status_utils', 'bot/helper/ext_utils/status_utils.py')
time_to_seconds = status_utils.time_to_seconds

class TestStatusUtils(unittest.TestCase):

    def test_time_to_seconds_hh_mm_ss(self):
        # Standard format
        self.assertEqual(time_to_seconds("01:02:03"), 3723.0)
        self.assertEqual(time_to_seconds("1:2:3"), 3723.0)

    def test_time_to_seconds_mm_ss(self):
        # MM:SS format
        self.assertEqual(time_to_seconds("02:03"), 123.0)
        self.assertEqual(time_to_seconds("2:3"), 123.0)

    def test_time_to_seconds_ss(self):
        # SS format
        self.assertEqual(time_to_seconds("03"), 3.0)
        self.assertEqual(time_to_seconds("3"), 3.0)

    def test_time_to_seconds_decimal(self):
        # Decimal seconds
        self.assertEqual(time_to_seconds("01:02:03.5"), 3723.5)
        self.assertEqual(time_to_seconds("02:03.5"), 123.5)
        self.assertEqual(time_to_seconds("03.5"), 3.5)

    def test_time_to_seconds_large_values(self):
        # Large values
        self.assertEqual(time_to_seconds("100:00:00"), 360000.0)

    def test_time_to_seconds_invalid_parts(self):
        # More than 3 parts
        self.assertEqual(time_to_seconds("1:2:3:4"), 0)

    def test_time_to_seconds_non_numeric(self):
        # Non-numeric parts
        self.assertEqual(time_to_seconds("abc"), 0)
        self.assertEqual(time_to_seconds("01:abc:03"), 0)
        self.assertEqual(time_to_seconds("01:02:abc"), 0)

    def test_time_to_seconds_edge_cases(self):
        # Empty string
        self.assertEqual(time_to_seconds(""), 0)
        # None input
        self.assertEqual(time_to_seconds(None), 0)
        # White spaces
        self.assertEqual(time_to_seconds(" 01:02:03 "), 3723.0)
        # Only colons
        self.assertEqual(time_to_seconds(":"), 0)
        self.assertEqual(time_to_seconds("::"), 0)

if __name__ == '__main__':
    unittest.main()
