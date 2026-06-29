from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from .crypto import decrypt_text, encrypt_text, generate_field_encryption_key, is_encrypted_value


class FieldEncryptionTests(SimpleTestCase):
    def test_generate_key_can_encrypt_and_decrypt(self):
        key = generate_field_encryption_key()
        with override_settings(FIELD_ENCRYPTION_KEY=key):
            encrypted = encrypt_text("Max Mustermann")
            self.assertTrue(is_encrypted_value(encrypted))
            self.assertNotIn("Max Mustermann", encrypted)
            self.assertEqual(decrypt_text(encrypted), "Max Mustermann")

    def test_empty_values_are_preserved(self):
        key = generate_field_encryption_key()
        with override_settings(FIELD_ENCRYPTION_KEY=key):
            self.assertEqual(encrypt_text(""), "")
            self.assertIsNone(encrypt_text(None))
            self.assertEqual(decrypt_text(""), "")
            self.assertIsNone(decrypt_text(None))

    def test_encrypt_is_idempotent_for_existing_ciphertext(self):
        key = generate_field_encryption_key()
        with override_settings(FIELD_ENCRYPTION_KEY=key):
            encrypted = encrypt_text("secret")
            self.assertEqual(encrypt_text(encrypted), encrypted)

    def test_missing_key_raises_clear_error(self):
        with override_settings(FIELD_ENCRYPTION_KEY=""):
            with self.assertRaises(ImproperlyConfigured):
                encrypt_text("secret")

    def test_invalid_key_raises_clear_error(self):
        with override_settings(FIELD_ENCRYPTION_KEY="not-a-fernet-key"):
            with self.assertRaises(ImproperlyConfigured):
                encrypt_text("secret")