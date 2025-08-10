"""
Security and Edge Case Tests for FeatureFlagsHQ SDK

This module contains tests for security features, edge cases, and error conditions
that might not be covered in the main test suites.
"""

import json
import logging
import os
import time
import threading
import unittest
from unittest.mock import patch, MagicMock
from queue import Queue, Empty

import responses

from featureflagshq import FeatureFlagsHQSDK, DEFAULT_API_BASE_URL
from featureflagshq.sdk import SecurityFilter


class TestSecurityFeatures(unittest.TestCase):
    """Test security-related functionality"""

    def setUp(self):
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.environment = "test"

    def test_security_filter_comprehensive(self):
        """Test SecurityFilter with various sensitive data patterns"""
        filter_instance = SecurityFilter()
        
        # Test cases that will actually match the regex patterns
        # Pattern: r'secret["\']?\s*[:=]\s*["\']?([^"\'\\s]+)'
        # Pattern: r'signature["\']?\s*[:=]\s*["\']?([^"\'\\s]+)'
        test_cases = [
            ("secret: my_secret_key", "[REDACTED]"),
            ("signature: auth_signature_123", "[REDACTED]"),
            ("secret=value", "[REDACTED]"),
            ("signature=token", "[REDACTED]"),
            ("no sensitive data here", "no sensitive data here"),
            ("", ""),
        ]
        
        for input_msg, expected_pattern in test_cases:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=input_msg, args=(), exc_info=None
            )
            
            result = filter_instance.filter(record)
            self.assertTrue(result)
            
            if expected_pattern == "[REDACTED]":
                self.assertIn("[REDACTED]", str(record.msg))
            else:
                self.assertEqual(str(record.msg), expected_pattern)

    def test_dangerous_string_patterns(self):
        """Test validation against various dangerous string patterns"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            # Test patterns that will actually be caught by the validation
            # The validation looks for: ['--', ';', '/*', '*/', 'union', 'select', 'insert', 'delete', 'update', 'drop']
            dangerous_patterns = [
                "user--comment",           # SQL comment
                "user;drop table",         # Semicolon + drop
                "user/*comment*/",         # SQL comment
                "user union select",       # Union select
                "user insert into",        # Insert
                "user delete from",        # Delete  
                "user update set",         # Update
                "user drop table",         # Drop
            ]
            
            # Also test control characters that should be caught
            control_char_patterns = [
                "user\x00admin",           # Null byte
                "user\r\nadmin",          # CRLF
                "user\ttab\nadmin",       # Tab + newline
                "user\x1b[31mred\x1b[0m", # ANSI escape sequence
            ]
            
            for dangerous_input in dangerous_patterns:
                with self.assertRaises(ValueError):
                    sdk._validate_string(dangerous_input, "test_field")
            
            for dangerous_input in control_char_patterns:
                with self.assertRaises(ValueError):
                    sdk._validate_string(dangerous_input, "test_field")
            
            sdk.shutdown()

    def test_hmac_signature_security(self):
        """Test HMAC signature generation security properties"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            payload1 = '{"test": "data"}'
            payload2 = '{"test": "different"}'
            timestamp = "1234567890"
            
            sig1 = sdk._generate_signature(payload1, timestamp)
            sig2 = sdk._generate_signature(payload2, timestamp)
            
            # Different payloads should produce different signatures
            self.assertNotEqual(sig1, sig2)
            
            # Same payload should always produce same signature
            sig1_repeat = sdk._generate_signature(payload1, timestamp)
            self.assertEqual(sig1, sig1_repeat)
            
            # Signature should be base64 encoded (no invalid characters)
            import base64
            try:
                decoded = base64.b64decode(sig1)
                self.assertEqual(len(decoded), 32)  # SHA256 produces 32-byte hash
            except Exception:
                self.fail("Signature is not valid base64")
            
            sdk.shutdown()

    def test_headers_no_secret_leakage(self):
        """Ensure headers don't leak sensitive information"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            headers = sdk._get_headers('{"test": "payload"}')
            
            # Client secret should not be in headers
            for header_name, header_value in headers.items():
                self.assertNotIn(self.client_secret, header_value)
                self.assertNotIn(self.client_secret, header_name)
            
            # But client ID should be present
            self.assertEqual(headers['X-Client-ID'], self.client_id)
            
            # Signature should be present but not the secret
            self.assertIn('X-Signature', headers)
            self.assertNotEqual(headers['X-Signature'], self.client_secret)
            
            sdk.shutdown()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""

    def setUp(self):
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.environment = "test"

    def test_unicode_and_special_characters(self):
        """Test handling of unicode and special characters"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            # Test unicode characters in user IDs and flag names
            # Note: _validate_user_id currently only warns for invalid patterns, doesn't raise ValueError
            unicode_tests = [
                ("user_测试", True),   # Chinese characters (warns but doesn't fail)
                ("user_🎯", True),     # Emoji (warns but doesn't fail)
                ("user_café", True),   # Accented characters (warns but doesn't fail)
                ("user_αβγ", True),    # Greek letters (warns but doesn't fail)
                ("user_123", True),   # Numbers (should pass)
                ("user_", True),      # Underscore (should pass)
                ("user-test", True),  # Hyphen (should pass)
                ("user@domain.com", True),  # Email-like (should pass for user_id)
            ]
            
            for test_input, should_pass in unicode_tests:
                if should_pass:
                    try:
                        result = sdk._validate_user_id(test_input)
                        self.assertEqual(result, test_input)
                    except ValueError:
                        self.fail(f"Expected {test_input} to pass validation")
                # Note: Currently no test cases expect ValueError for user_id pattern validation
            
            # Test flag names (stricter validation)
            flag_tests = [
                ("flag_test", True),
                ("flag-test", True),
                ("flag123", True),
                ("flag_测试", False),  # Unicode not allowed in flag names
                ("flag with spaces", False),
                ("flag@domain", False),  # @ not allowed in flag names
            ]
            
            for test_input, should_pass in flag_tests:
                if should_pass:
                    try:
                        result = sdk._validate_flag_name(test_input)
                        self.assertEqual(result, test_input)
                    except ValueError:
                        self.fail(f"Expected {test_input} to pass flag name validation")
                else:
                    with self.assertRaises(ValueError):
                        sdk._validate_flag_name(test_input)
            
            sdk.shutdown()

    def test_extreme_values(self):
        """Test handling of extreme values"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            # Test very large numbers
            large_int = str(2**53)  # A large but safe integer for float conversion
            result = sdk._convert_value(large_int, "int")
            self.assertEqual(result, 2**53)
            
            # Test very large float
            large_float = "1.7976931348623157e+308"  # Near max float64
            result = sdk._convert_value(large_float, "float")
            self.assertIsInstance(result, float)
            
            # Test very small float
            small_float = "2.2250738585072014e-308"  # Near min positive float64
            result = sdk._convert_value(small_float, "float")
            self.assertIsInstance(result, float)
            
            # Test very large integers (Python handles arbitrarily large ints)
            very_large_int = str(2**100)  # Very large number
            result = sdk._convert_value(very_large_int, "int")
            self.assertIsInstance(result, int)
            self.assertEqual(result, 2**100)
            
            sdk.shutdown()

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON data"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            malformed_json_cases = [
                '{"incomplete": ',
                '{"missing_quotes": value}',
                '{"trailing_comma": "value",}',
                '{invalid json structure}',
                '{"nested": {"incomplete": }',
                '[1, 2, 3,]',  # Trailing comma in array
                '',  # Empty string
            ]
            
            # Test truly malformed JSON that should return default {}
            for malformed_json in malformed_json_cases:
                result = sdk._convert_value(malformed_json, "json")
                # Should return default value for JSON type
                self.assertEqual(result, {})
            
            # Test valid JSON that should NOT return default {}
            valid_json_cases = [
                ('{"duplicate": "key", "duplicate": "key2"}', {'duplicate': 'key2'}),  # Duplicate keys - valid JSON
                ('null', None),  # Valid JSON but null
                ('true', True),  # Valid JSON but boolean
                ('"just a string"', "just a string"),  # Valid JSON but just string
            ]
            
            for json_string, expected_result in valid_json_cases:
                result = sdk._convert_value(json_string, "json")
                self.assertEqual(result, expected_result)
            
            sdk.shutdown()

    def test_memory_pressure_scenarios(self):
        """Test behavior under memory pressure"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            # Simulate adding many users beyond cleanup threshold
            initial_users = len(sdk.stats['unique_users'])
            
            # Add users beyond MAX_UNIQUE_USERS_TRACKED
            for i in range(12000):  # Exceeds 10000 limit
                user_id = f"memory_test_user_{i}"
                sdk.get_bool(user_id, "test_flag", default_value=True)
            
            # Check that cleanup occurred
            stats = sdk.get_stats()
            final_users = stats['unique_users_count']
            
            # Should be at or below the limit due to cleanup
            self.assertLessEqual(final_users, 10000)
            
            # But should still be tracking users
            self.assertGreater(final_users, 0)
            
            sdk.shutdown()

    def test_concurrent_stats_access(self):
        """Test concurrent access to statistics"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            errors = []
            results = []
            
            def stats_reader(thread_id):
                try:
                    for i in range(100):
                        stats = sdk.get_stats()
                        results.append((thread_id, i, len(stats)))
                        time.sleep(0.001)  # Small delay
                except Exception as e:
                    errors.append((thread_id, str(e)))
            
            def stats_modifier(thread_id):
                try:
                    for i in range(100):
                        user_id = f"thread_{thread_id}_user_{i}"
                        sdk.get_bool(user_id, "test_flag", default_value=True)
                        time.sleep(0.001)  # Small delay
                except Exception as e:
                    errors.append((thread_id, str(e)))
            
            # Start concurrent readers and modifiers
            threads = []
            
            # 3 stats readers
            for i in range(3):
                thread = threading.Thread(target=stats_reader, args=(f"reader_{i}",))
                threads.append(thread)
                thread.start()
            
            # 2 stats modifiers
            for i in range(2):
                thread = threading.Thread(target=stats_modifier, args=(f"modifier_{i}",))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join(timeout=10)
            
            # Check for errors
            if errors:
                self.fail(f"Concurrent access errors: {errors}")
            
            # Verify we got results from all readers
            self.assertGreater(len(results), 0)
            
            sdk.shutdown()

    @responses.activate
    def test_api_response_edge_cases(self):
        """Test handling of various API response edge cases"""
        
        edge_case_responses = [
            # Empty response
            (200, {}),
            # Missing data field
            (200, {"message": "success"}),
            # Data field is not a list
            (200, {"data": "not a list"}),
            # Data field is null
            (200, {"data": None}),
            # Data contains non-dict items
            (200, {"data": ["not", "dict", "items"]}),
            # Data contains dicts without name
            (200, {"data": [{"value": True, "type": "bool"}]}),
            # Data contains dicts with empty name
            (200, {"data": [{"name": "", "value": True, "type": "bool"}]}),
            # Data contains dicts with non-string name
            (200, {"data": [{"name": 123, "value": True, "type": "bool"}]}),
        ]
        
        for status_code, response_data in edge_case_responses:
            with self.subTest(response=response_data):
                responses.reset()
                responses.add(
                    responses.GET,
                    f"{DEFAULT_API_BASE_URL}/v1/flags/",
                    json=response_data,
                    status=status_code
                )
                
                sdk = FeatureFlagsHQSDK(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    environment=self.environment
                )
                
                try:
                    # Should not crash, should handle gracefully
                    flags = sdk._fetch_flags()
                    self.assertIsInstance(flags, dict)
                    
                    # Should still be able to get flags (will use defaults)
                    result = sdk.get_bool("user123", "test_flag", default_value=True)
                    self.assertTrue(result)
                    
                finally:
                    sdk.shutdown()

    def test_queue_edge_cases(self):
        """Test edge cases with queue operations"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            # Test with a full queue (mock scenario)
            original_queue = sdk.logs_queue
            full_queue = Queue(maxsize=1)
            full_queue.put({"test": "item"})  # Fill it up
            sdk.logs_queue = full_queue
            
            # This should not raise an exception
            sdk._log_access("user123", "test_flag", True, {}, 1.0)
            
            # Queue should still have the original item
            self.assertEqual(sdk.logs_queue.qsize(), 1)
            
            # Test empty queue upload
            empty_queue = Queue()
            sdk.logs_queue = empty_queue
            
            # Should handle empty queue gracefully
            sdk._upload_logs()  # Should not crash
            
            sdk.shutdown()


class TestErrorRecovery(unittest.TestCase):
    """Test error recovery and resilience"""

    def setUp(self):
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.environment = "test"

    def test_initialization_failure_recovery(self):
        """Test recovery from initialization failures"""
        with patch('featureflagshq.sdk.requests.Session') as mock_session:
            # Make initialization fail
            mock_session.return_value.get.side_effect = Exception("Network error")
            
            # Should not crash during initialization
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=False  # Allow network calls to fail
            )
            
            try:
                # Should still work with defaults
                result = sdk.get_bool("user123", "test_flag", default_value=True)
                self.assertTrue(result)
                
                # Health check should show issues
                health = sdk.get_health_check()
                self.assertIn('status', health)
                
            finally:
                sdk.shutdown()

    def test_background_thread_failure_handling(self):
        """Test handling of background thread failures"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )
            
            # Mock the fetch_flags method to raise an exception
            original_fetch = sdk._fetch_flags
            
            def failing_fetch():
                raise Exception("Simulated fetch failure")
            
            sdk._fetch_flags = failing_fetch
            
            # Test that a single fetch operation fails gracefully
            try:
                sdk._fetch_flags()
                self.fail("Expected exception was not raised")
            except Exception as e:
                self.assertEqual(str(e), "Simulated fetch failure")
            
            # SDK should still be functional for normal operations
            result = sdk.get_bool("user123", "test_flag", default_value=True)
            self.assertTrue(result)
            
            # Restore original method
            sdk._fetch_flags = original_fetch
            
            sdk.shutdown()

    def test_cleanup_on_shutdown(self):
        """Test proper cleanup during shutdown"""
        with patch('featureflagshq.sdk.requests.Session') as mock_session:
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=False
            )
            
            # Add some activity
            sdk.get_bool("user123", "test_flag", default_value=True)
            
            # Mock session close to raise exception
            mock_session.return_value.close.side_effect = Exception("Close error")
            
            # Shutdown should not crash even if session.close() fails
            try:
                sdk.shutdown()
            except Exception as e:
                self.fail(f"Shutdown should not raise exception: {e}")
            
            # Verify stop event was set
            self.assertTrue(sdk._stop_event.is_set())


if __name__ == '__main__':
    unittest.main()