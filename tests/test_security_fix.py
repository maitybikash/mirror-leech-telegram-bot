import os
import sys
import hashlib
import hmac
import unittest
import logging

class TestSecurityFix(unittest.TestCase):
    def setUp(self):
        if 'config' in sys.modules:
            del sys.modules['config']
        if 'TELEGRAM_HASH' in os.environ:
            del os.environ['TELEGRAM_HASH']

    def test_verify_pin_consistency(self):
        # Set a hash
        os.environ['TELEGRAM_HASH'] = 'consistency_check'

        # Import verify_pin from wserver
        from web.wserver import verify_pin, get_telegram_hash

        # Import Config from bot
        # This will load bot module
        from bot.core.config_manager import Config

        # We need to manually set Config.TELEGRAM_HASH because Config.load() is not called automatically
        Config.TELEGRAM_HASH = 'consistency_check'

        gid = "test_gid_123"
        pin_from_config = Config.get_pin(gid)

        # Verify wserver logic accepts this pin
        self.assertTrue(verify_pin(gid, pin_from_config))

        # Check if hash retrieval matches
        self.assertEqual(get_telegram_hash(), Config.TELEGRAM_HASH)

    def test_verify_pin_logic(self):
        os.environ['TELEGRAM_HASH'] = 'my_secret_hash'
        from web.wserver import verify_pin
        gid = "1234567890abcdef"
        key = b'my_secret_hash'
        msg = gid.encode()
        expected_pin = hmac.new(key, msg, hashlib.sha256).hexdigest()[:6]
        self.assertTrue(verify_pin(gid, expected_pin))
        self.assertFalse(verify_pin(gid, "wrongpin"))

if __name__ == '__main__':
    unittest.main()
