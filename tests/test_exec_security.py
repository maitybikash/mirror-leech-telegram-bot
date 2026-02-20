import sys
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mock modules to avoid loading the entire bot
sys.modules['aiofiles'] = MagicMock()
sys.modules['bot'] = MagicMock()
sys.modules['bot.core'] = MagicMock()
sys.modules['bot.core.telegram_manager'] = MagicMock()
sys.modules['bot.helper'] = MagicMock()
sys.modules['bot.helper.ext_utils'] = MagicMock()
sys.modules['bot.helper.ext_utils.bot_utils'] = MagicMock()
sys.modules['bot.helper.telegram_helper'] = MagicMock()
sys.modules['bot.helper.telegram_helper.message_utils'] = MagicMock()

# Mock specific attributes used in exec.py
sys.modules['bot'].LOGGER = MagicMock()
sys.modules['bot.core.telegram_manager'].TgClient = MagicMock()
sys.modules['bot.core.telegram_manager'].TgClient.bot = MagicMock()

# Mock Config
sys.modules['bot.core.config_manager'] = MagicMock()
sys.modules['bot.core.config_manager'].Config = MagicMock()
# Set OWNER_ID to something different from attacker
sys.modules['bot.core.config_manager'].Config.OWNER_ID = 11111

# Mock async utils
async def async_mock(*args, **kwargs):
    return MagicMock()

async def simple_sync_to_async(func, *args, **kwargs):
    return func(*args, **kwargs)

sys.modules['bot.helper.ext_utils.bot_utils'].sync_to_async = simple_sync_to_async
sys.modules['bot.helper.ext_utils.bot_utils'].new_task = lambda x: x
sys.modules['bot.helper.telegram_helper.message_utils'].send_file = async_mock
sys.modules['bot.helper.telegram_helper.message_utils'].send_message = async_mock

# Now we can import the module under test
# We need to make sure the relative imports work.
# Since we are running this script, we need to add the repo root to sys.path
import os
sys.path.insert(0, os.getcwd())

# We need to simulate the package structure for relative imports to work
# or we can import the file directly using importlib
# But relative imports require __package__ to be set.
# The easiest way is to mock the `bot.modules` package and `bot.modules.exec` module in sys.modules,
# then load the code from file and exec it into that module namespace.

import importlib.util
spec = importlib.util.spec_from_file_location("bot.modules.exec", "bot/modules/exec.py")
exec_module = importlib.util.module_from_spec(spec)
sys.modules["bot.modules.exec"] = exec_module
spec.loader.exec_module(exec_module)

# Now we have the module loaded with mocked dependencies.
# Let's test the 'do' function.

async def test_vulnerability():
    print("Testing vulnerability...")

    # Define a mock message
    mock_message = MagicMock()
    mock_message.text = "/exec print('VULNERABILITY_EXPLOITED')"
    mock_message.chat.id = 12345
    mock_message.from_user.id = 99999 # Attacker ID
    mock_message.sender_chat = None

    # Mock Config.OWNER_ID effectively being something else
    # But wait, exec.py doesn't import Config yet. So we can't mock it there.
    # The vulnerability is that it DOES NOT check Config.OWNER_ID.

    # We need to capture the output.
    # The do function captures stdout.

    result = await exec_module.do("exec", mock_message)

    print(f"Result: {result}")

    if "VULNERABILITY_EXPLOITED" in str(result):
        print("VULNERABILITY CONFIRMED: Code executed for non-owner.")
    else:
        print("VULNERABILITY NOT CONFIRMED: Code did not execute.")

async def test_legitimate_usage():
    print("\nTesting legitimate usage...")

    # Define a mock message
    mock_message = MagicMock()
    mock_message.text = "/exec print('LEGITIMATE_CODE')"
    mock_message.chat.id = 12345
    mock_message.from_user.id = 11111 # Owner ID
    mock_message.sender_chat = None

    # We need to capture the output.
    # The do function captures stdout.

    result = await exec_module.do("exec", mock_message)

    print(f"Result: {result}")

    if "LEGITIMATE_CODE" in str(result):
        print("LEGITIMATE USAGE CONFIRMED: Code executed for owner.")
    else:
        print("LEGITIMATE USAGE FAILED: Code did not execute.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_vulnerability())
    loop.run_until_complete(test_legitimate_usage())
