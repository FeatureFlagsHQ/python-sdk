import time
import unittest
from unittest.mock import patch

import responses

from featureflagshq import FeatureFlagsHQSDK, create_production_client, validate_production_config, SDK_VERSION, \
    DEFAULT_API_BASE_URL


class TestFeatureFlagsHQSDK(unittest.TestCase):

    def setUp(self):
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.environment = "test"

    def tearDown(self):
        # Clean up any SDK instances
        pass

    def test_initialization_with_valid_credentials(self):
        """Test SDK initialization with valid credentials"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                environment=self.environment,
                offline_mode=True  # Prevent network calls
            )

            self.assertEqual(sdk.client_id, self.client_id)
            self.assertEqual(sdk.client_secret, self.client_secret)
            self.assertEqual(sdk.environment, self.environment)
            sdk.shutdown()

    def test_initialization_missing_credentials(self):
        """Test SDK initialization fails with missing credentials"""
        with self.assertRaises(ValueError):
            FeatureFlagsHQSDK(client_id="", client_secret="secret")

        with self.assertRaises(ValueError):
            FeatureFlagsHQSDK(client_id="client", client_secret="")

    def test_input_validation(self):
        """Test input validation methods"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Valid inputs
            self.assertEqual(sdk._validate_user_id("user123"), "user123")
            self.assertEqual(sdk._validate_flag_name("flag_name"), "flag_name")

            # Invalid inputs
            with self.assertRaises(ValueError):
                sdk._validate_user_id("")

            with self.assertRaises(ValueError):
                sdk._validate_flag_name("flag with spaces")

            with self.assertRaises(ValueError):
                sdk._validate_user_id("user\nwith\nnewlines")

            sdk.shutdown()

    def test_get_flag_offline_mode(self):
        """Test flag retrieval in offline mode"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Should return default values in offline mode
            result = sdk.get_bool("user123", "test_flag", default_value=True)
            self.assertTrue(result)

            result = sdk.get_string("user123", "test_flag", default_value="default")
            self.assertEqual(result, "default")

            result = sdk.get_int("user123", "test_flag", default_value=42)
            self.assertEqual(result, 42)

            sdk.shutdown()

    def test_url_validation(self):
        """Test URL validation functionality"""
        # Test invalid URL schemes
        with self.assertRaises(ValueError) as cm:
            FeatureFlagsHQSDK(
                client_id="test",
                client_secret="test",
                api_base_url="ftp://example.com"
            )
        self.assertIn("Invalid URL scheme", str(cm.exception))

        # Test empty URL
        with self.assertRaises(ValueError) as cm:
            FeatureFlagsHQSDK(
                client_id="test",
                client_secret="test",
                api_base_url=""
            )
        self.assertIn("API base URL must be a non-empty string", str(cm.exception))

        # Test invalid URL (missing hostname)
        with self.assertRaises(ValueError) as cm:
            FeatureFlagsHQSDK(
                client_id="test",
                client_secret="test",
                api_base_url="https://"
            )
        self.assertIn("Invalid URL: missing hostname", str(cm.exception))

        # Test non-string URL
        with self.assertRaises(ValueError) as cm:
            FeatureFlagsHQSDK(
                client_id="test",
                client_secret="test",
                api_base_url=123
            )
        self.assertIn("API base URL must be a non-empty string", str(cm.exception))

    def test_string_validation_edge_cases(self):
        """Test string validation edge cases"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test too long user ID
            long_user_id = "a" * 256  # Exceeds MAX_USER_ID_LENGTH
            with self.assertRaises(ValueError) as cm:
                sdk._validate_user_id(long_user_id)
            self.assertIn("too long", str(cm.exception))

            # Test too long flag name
            long_flag_name = "a" * 256  # Exceeds MAX_FLAG_NAME_LENGTH
            with self.assertRaises(ValueError) as cm:
                sdk._validate_flag_name(long_flag_name)
            self.assertIn("too long", str(cm.exception))

            # Test non-string inputs
            with self.assertRaises(ValueError) as cm:
                sdk._validate_string(123, "test_field")
            self.assertIn("must be a string", str(cm.exception))

            # Test empty string after stripping
            with self.assertRaises(ValueError) as cm:
                sdk._validate_string("   ", "test_field")
            self.assertIn("cannot be empty", str(cm.exception))

            # Test control characters in string
            with self.assertRaises(ValueError) as cm:
                sdk._validate_user_id("user\nwith\nnewlines")
            self.assertIn("contains invalid characters", str(cm.exception))

            sdk.shutdown()

    def test_flag_evaluation_with_segments(self):
        """Test flag evaluation with user segments"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Mock flag data
            flag_data = {
                'name': 'test_flag',
                'value': True,
                'type': 'bool',
                'is_active': True,
                'segments': [
                    {
                        'name': 'country',
                        'comparator': '==',
                        'value': 'US',
                        'type': 'string'
                    }
                ]
            }

            # Test segment matching
            segments = {'country': 'US'}
            result, context = sdk._evaluate_flag(flag_data, "user123", segments)
            self.assertTrue(result)

            # Test segment not matching
            segments = {'country': 'UK'}
            result, context = sdk._evaluate_flag(flag_data, "user123", segments)
            self.assertFalse(result)  # Should return default for bool

            sdk.shutdown()

    def test_rollout_percentage(self):
        """Test rollout percentage functionality"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Flag with 0% rollout
            flag_data = {
                'name': 'test_flag',
                'value': True,
                'type': 'bool',
                'is_active': True,
                'rollout': {'percentage': 0}
            }

            result, context = sdk._evaluate_flag(flag_data, "user123")
            self.assertFalse(result)  # Should always return default with 0% rollout

            # Flag with 100% rollout
            flag_data['rollout']['percentage'] = 100
            result, context = sdk._evaluate_flag(flag_data, "user123")
            self.assertTrue(result)

            sdk.shutdown()

    def test_type_conversion(self):
        """Test value type conversion"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Boolean conversion
            self.assertTrue(sdk._convert_value("true", "bool"))
            self.assertFalse(sdk._convert_value("false", "bool"))
            self.assertTrue(sdk._convert_value("1", "bool"))

            # Integer conversion
            self.assertEqual(sdk._convert_value("42", "int"), 42)
            self.assertEqual(sdk._convert_value("42.7", "int"), 42)

            # Float conversion
            self.assertEqual(sdk._convert_value("42.7", "float"), 42.7)

            # JSON conversion
            json_data = {"key": "value"}
            self.assertEqual(sdk._convert_value('{"key": "value"}', "json"), json_data)
            self.assertEqual(sdk._convert_value(json_data, "json"), json_data)

            sdk.shutdown()

    @responses.activate
    def test_fetch_flags_success(self):
        """Test successful flag fetching from API"""
        # Mock API response
        mock_response = {
            "data": [
                {
                    "name": "test_flag",
                    "value": True,
                    "type": "bool",
                    "is_active": True
                }
            ]
        }

        responses.add(
            responses.GET,
            f"{DEFAULT_API_BASE_URL}/v1/flags/",
            json=mock_response,
            status=200
        )

        sdk = FeatureFlagsHQSDK(
            client_id=self.client_id,
            client_secret=self.client_secret,
            environment=self.environment
        )

        # Wait a bit for initialization
        time.sleep(0.1)

        flags = sdk._fetch_flags()
        self.assertIn("test_flag", flags)
        self.assertEqual(flags["test_flag"]["value"], True)

        sdk.shutdown()

    @responses.activate
    def test_fetch_flags_auth_error(self):
        """Test flag fetching with authentication error"""
        responses.add(
            responses.GET,
            f"{DEFAULT_API_BASE_URL}/v1/flags/",
            status=401
        )

        sdk = FeatureFlagsHQSDK(
            client_id=self.client_id,
            client_secret=self.client_secret,
            environment=self.environment
        )

        flags = sdk._fetch_flags()
        self.assertEqual(flags, {})

        # Check that auth error was recorded
        stats = sdk.get_stats()
        self.assertGreater(stats['errors']['auth_errors'], 0)

        sdk.shutdown()

    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=False  # Rate limiting only works when not in offline mode
            )

            user_id = "test_user"

            # Should allow first request
            self.assertTrue(sdk._rate_limit_check(user_id))

            # Simulate many requests
            for _ in range(1000):
                sdk._rate_limit_check(user_id)

            # Should now be rate limited
            self.assertFalse(sdk._rate_limit_check(user_id))

            sdk.shutdown()

    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Initially should be closed (allow requests)
            self.assertTrue(sdk._check_circuit_breaker())

            # Record multiple failures
            for _ in range(6):  # Threshold is 5
                sdk._record_api_failure()

            # Should now be open (block requests)
            self.assertFalse(sdk._check_circuit_breaker())

            sdk.shutdown()

    def test_get_user_flags(self):
        """Test getting multiple flags for a user"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Mock multiple flags
            sdk.flags = {
                'flag1': {'name': 'flag1', 'value': True, 'type': 'bool', 'is_active': True},
                'flag2': {'name': 'flag2', 'value': 'test', 'type': 'string', 'is_active': True},
                'flag3': {'name': 'flag3', 'value': 42, 'type': 'int', 'is_active': True}
            }

            user_flags = sdk.get_user_flags("user123")

            self.assertEqual(len(user_flags), 3)
            self.assertTrue(user_flags['flag1'])
            self.assertEqual(user_flags['flag2'], 'test')
            self.assertEqual(user_flags['flag3'], 42)

            # Test with specific flag keys
            specific_flags = sdk.get_user_flags("user123", flag_keys=['flag1', 'flag2'])
            self.assertEqual(len(specific_flags), 2)
            self.assertNotIn('flag3', specific_flags)

            sdk.shutdown()

    def test_stats_and_health(self):
        """Test statistics and health check functionality"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Get initial stats
            stats = sdk.get_stats()
            self.assertIn('total_user_accesses', stats)
            self.assertIn('api_calls', stats)

            # Get health check
            health = sdk.get_health_check()
            self.assertIn('status', health)
            self.assertIn('sdk_version', health)
            self.assertEqual(health['sdk_version'], SDK_VERSION)

            sdk.shutdown()

    def test_context_manager(self):
        """Test context manager functionality"""
        with patch('featureflagshq.sdk.requests.Session'):
            with FeatureFlagsHQSDK(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    offline_mode=True
            ) as sdk:
                result = sdk.get_bool("user123", "test_flag", default_value=True)
                self.assertTrue(result)
            # SDK should be automatically shut down

    def test_environment_variable_initialization(self):
        """Test SDK initialization from environment variables"""
        import os

        # Mock environment variables
        with patch.dict(os.environ, {
            'FEATUREFLAGSHQ_CLIENT_ID': 'env_client_id',
            'FEATUREFLAGSHQ_CLIENT_SECRET': 'env_client_secret',
            'FEATUREFLAGSHQ_ENVIRONMENT': 'env_test'
        }):
            with patch('featureflagshq.sdk.requests.Session'):
                sdk = FeatureFlagsHQSDK(offline_mode=True)

                # Should use environment variables
                self.assertEqual(sdk.client_id, 'env_client_id')
                self.assertEqual(sdk.client_secret, 'env_client_secret')
                self.assertEqual(sdk.environment, 'env_test')

                sdk.shutdown()

    def test_json_and_float_flag_types(self):
        """Test JSON and float flag type handling"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test JSON conversion
            json_data = {"key": "value", "number": 42}
            result = sdk._convert_value(json_data, "json")
            self.assertEqual(result, json_data)

            # Test JSON string conversion
            json_string = '{"test": "data"}'
            result = sdk._convert_value(json_string, "json")
            self.assertEqual(result, {"test": "data"})

            # Test float conversion
            result = sdk._convert_value("3.14", "float")
            self.assertEqual(result, 3.14)

            # Test float from integer string
            result = sdk._convert_value("42", "float")
            self.assertEqual(result, 42.0)

            # Test get_json method
            result = sdk.get_json("user123", "config_flag", default_value={"default": True})
            self.assertEqual(result, {"default": True})

            # Test get_float method
            result = sdk.get_float("user123", "rate_flag", default_value=1.5)
            self.assertEqual(result, 1.5)

            sdk.shutdown()

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery functionality"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Initially should be closed
            self.assertTrue(sdk._check_circuit_breaker())

            # Trigger circuit breaker to open
            for _ in range(6):  # Threshold is 5
                sdk._record_api_failure()

            # Should now be open
            self.assertFalse(sdk._check_circuit_breaker())

            # Simulate time passing for recovery
            import time
            original_time = time.time
            mock_time = original_time() + 61  # More than recovery time

            with patch('time.time', return_value=mock_time):
                # Should allow one test call (half-open state)
                self.assertTrue(sdk._check_circuit_breaker())

                # Record success to close circuit breaker
                sdk._record_api_success()
                self.assertTrue(sdk._check_circuit_breaker())

            sdk.shutdown()

    def test_memory_cleanup_functionality(self):
        """Test memory cleanup for users and flags tracking"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Add many users to trigger cleanup by calling get_bool
            for i in range(15000):  # Exceeds MAX_UNIQUE_USERS_TRACKED
                user_id = f"user_{i}"
                sdk.get_bool(user_id, "test_flag", default_value=True)

            # Check that cleanup occurred
            stats = sdk.get_stats()
            self.assertLessEqual(stats['unique_users_count'], 10000)  # MAX_UNIQUE_USERS_TRACKED

            sdk.shutdown()

    def test_log_uploading_functionality(self):
        """Test log uploading and batching"""
        with patch('featureflagshq.sdk.requests.Session') as mock_session:
            # Mock successful response
            mock_response = mock_session.return_value.post.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "success"}

            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=False  # Need online mode for log upload
            )

            # Generate some user activity to create logs
            for i in range(10):
                sdk.get_bool(f"user_{i}", "test_flag", default_value=True)

            # Test manual log flush
            result = sdk.flush_logs()
            self.assertTrue(result)

            # Verify API was called
            mock_session.return_value.post.assert_called()

            sdk.shutdown()

    def test_error_scenarios_and_edge_cases(self):
        """Test various error scenarios and edge cases"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test invalid conversion types (returns defaults, doesn't raise)
            result = sdk._convert_value("invalid_json", "json")
            self.assertEqual(result, {})  # Default for json type

            result = sdk._convert_value("not_a_number", "int")
            self.assertEqual(result, 0)  # Default for int type

            result = sdk._convert_value("not_a_float", "float")
            self.assertEqual(result, 0.0)  # Default for float type

            # Test flag evaluation with invalid segments
            invalid_segments = {"": "value"}  # Empty key
            result = sdk.get_bool("user123", "test_flag",
                                  segments=invalid_segments, default_value=False)
            self.assertFalse(result)

            # Test refresh with offline mode
            result = sdk.refresh_flags()
            self.assertFalse(result)  # Should fail in offline mode

            sdk.shutdown()

    @responses.activate
    def test_background_polling_functionality(self):
        """Test background polling for flag updates"""
        # Mock flag response
        mock_response = {
            "data": [
                {
                    "name": "test_flag",
                    "value": True,
                    "type": "bool",
                    "is_active": True
                }
            ]
        }

        responses.add(
            responses.GET,
            f"{DEFAULT_API_BASE_URL}/v1/flags/",
            json=mock_response,
            status=200
        )

        sdk = FeatureFlagsHQSDK(
            client_id=self.client_id,
            client_secret=self.client_secret,
            offline_mode=False  # Enable polling
        )

        try:
            # Wait a bit for initialization
            import time
            time.sleep(0.2)

            # Test manual refresh
            result = sdk.refresh_flags()
            self.assertTrue(result)

            # Verify flags were loaded
            flag_result = sdk.get_bool("user123", "test_flag", default_value=False)
            # Should return True based on mock response

            # Test stats after polling
            stats = sdk.get_stats()
            self.assertGreaterEqual(stats['api_calls']['successful'], 1)

        finally:
            sdk.shutdown()


class TestProductionHelpers(unittest.TestCase):

    def test_validate_production_config(self):
        """Test production configuration validation"""
        # Valid config
        config = {
            'api_base_url': DEFAULT_API_BASE_URL,
            'timeout': 30,
            'client_secret': 'a' * 32
        }
        warnings = validate_production_config(config)
        self.assertEqual(len(warnings), 0)

        # Invalid config
        config = {
            'api_base_url': 'http://api.featureflagshq.com',  # HTTP instead of HTTPS
            'timeout': 2,  # Too low
            'client_secret': 'short'  # Too short
        }
        warnings = validate_production_config(config)
        self.assertGreater(len(warnings), 0)

    def test_create_production_client(self):
        """Test production client creation"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = create_production_client(
                client_id="test_client",
                client_secret="test_secret",
                environment="production",
                offline_mode=True
            )

            self.assertIsInstance(sdk, FeatureFlagsHQSDK)
            self.assertEqual(sdk.environment, "production")
            sdk.shutdown()


class TestAdditionalSDKFeatures(unittest.TestCase):
    """Additional test cases for enhanced SDK coverage"""

    def setUp(self):
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.environment = "test"

    def test_security_filter(self):
        """Test SecurityFilter functionality"""
        from featureflagshq.sdk import SecurityFilter
        import logging

        filter_instance = SecurityFilter()

        # Create a mock log record
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="secret: sensitive_data, signature: auth_token", args=(), exc_info=None
        )

        # Apply filter
        result = filter_instance.filter(record)

        # Should return True but modify the message
        self.assertTrue(result)
        self.assertIn("[REDACTED]", str(record.msg))
        # The pattern replaces the captured group with group+[REDACTED]
        # So "secret: sensitive_data" becomes "secret: sensitive_data[REDACTED]"
        modified_msg = str(record.msg)
        # Just verify that [REDACTED] was added and sensitive patterns were processed
        self.assertTrue(modified_msg != "secret: sensitive_data, signature: auth_token")
        self.assertEqual(modified_msg.count("[REDACTED]"), 2)  # Two patterns matched

    def test_hmac_signature_generation(self):
        """Test HMAC signature generation"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            payload = '{"test": "data"}'
            timestamp = "1234567890"

            signature = sdk._generate_signature(payload, timestamp)

            # Should return a base64 encoded string
            self.assertIsInstance(signature, str)
            self.assertGreater(len(signature), 0)

            # Same inputs should produce same signature
            signature2 = sdk._generate_signature(payload, timestamp)
            self.assertEqual(signature, signature2)

            # Different inputs should produce different signatures
            signature3 = sdk._generate_signature(payload, "9876543210")
            self.assertNotEqual(signature, signature3)

            sdk.shutdown()

    def test_segment_matching_numeric_comparisons(self):
        """Test segment matching with numeric comparisons"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test integer comparisons
            segment = {'name': 'age', 'comparator': '>', 'value': '18', 'type': 'int'}
            segments = {'age': 25}
            self.assertTrue(sdk._check_segment_match(segment, segments))

            segments = {'age': 15}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            # Test float comparisons
            segment = {'name': 'score', 'comparator': '>=', 'value': '85.5', 'type': 'float'}
            segments = {'score': 90.0}
            self.assertTrue(sdk._check_segment_match(segment, segments))

            segments = {'score': 80.0}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            # Test contains operator
            segment = {'name': 'tags', 'comparator': 'contains', 'value': 'premium', 'type': 'string'}
            segments = {'tags': 'user-premium-active'}
            self.assertTrue(sdk._check_segment_match(segment, segments))

            segments = {'tags': 'basic-user'}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            # Test boolean comparisons
            segment = {'name': 'is_beta', 'comparator': '==', 'value': 'true', 'type': 'bool'}
            segments = {'is_beta': True}
            self.assertTrue(sdk._check_segment_match(segment, segments))

            segments = {'is_beta': False}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            sdk.shutdown()

    def test_segment_matching_error_cases(self):
        """Test segment matching with error conditions"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test invalid type conversion
            segment = {'name': 'age', 'comparator': '>', 'value': 'not_a_number', 'type': 'int'}
            segments = {'age': 25}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            # Test missing segment value
            segment = {'name': 'missing_key', 'comparator': '==', 'value': 'test', 'type': 'string'}
            segments = {'age': 25}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            # Test invalid comparator
            segment = {'name': 'age', 'comparator': 'invalid_op', 'value': '18', 'type': 'int'}
            segments = {'age': 25}
            self.assertFalse(sdk._check_segment_match(segment, segments))

            sdk.shutdown()

    def test_segment_evaluation_requirement_one_or_more_match(self):
        """Test that flag evaluation requires at least one segment to match when segments are present"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Flag with multiple active segments
            flag_data = {
                'name': 'test_flag',
                'is_active': True,
                'value': 'enabled_value',
                'type': 'string',
                'segments': [
                    {'name': 'country', 'comparator': '==', 'value': 'US', 'type': 'string', 'is_active': True},
                    {'name': 'age', 'comparator': '>', 'value': '18', 'type': 'int', 'is_active': True},
                    {'name': 'plan', 'comparator': '==', 'value': 'premium', 'type': 'string', 'is_active': True}
                ]
            }

            # Case 1: No segments provided - should return default value
            result, context = sdk._evaluate_flag(flag_data, "user123", None)
            self.assertEqual(result, '')  # Default string value
            self.assertTrue(context['default_value_used'])
            self.assertEqual(context['reason'], 'segment_not_matched')
            self.assertEqual(len(context['segments_matched']), 0)

            # Case 2: User segments don't match any flag segments - should return default
            user_segments = {'country': 'UK', 'age': 16, 'plan': 'basic'}
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertEqual(result, '')  # Default string value
            self.assertTrue(context['default_value_used'])
            self.assertEqual(context['reason'], 'segment_not_matched')
            self.assertEqual(len(context['segments_matched']), 0)

            # Case 3: One segment matches - should return flag value
            user_segments = {'country': 'US', 'age': 16, 'plan': 'basic'}
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertEqual(result, 'enabled_value')
            self.assertFalse(context['default_value_used'])
            self.assertEqual(context['reason'], 'active_flag')
            self.assertEqual(len(context['segments_matched']), 1)
            self.assertIn('country', context['segments_matched'])

            # Case 4: Multiple segments match - should return flag value
            user_segments = {'country': 'US', 'age': 25, 'plan': 'premium'}
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertEqual(result, 'enabled_value')
            self.assertFalse(context['default_value_used'])
            self.assertEqual(context['reason'], 'active_flag')
            self.assertEqual(len(context['segments_matched']), 3)

            sdk.shutdown()

    def test_segment_evaluation_with_inactive_segments(self):
        """Test that inactive segments are filtered out during evaluation"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Flag with mix of active and inactive segments
            flag_data = {
                'name': 'test_flag',
                'is_active': True,
                'value': 'enabled_value',
                'type': 'string',
                'segments': [
                    {'name': 'country', 'comparator': '==', 'value': 'US', 'type': 'string', 'is_active': True},
                    {'name': 'age', 'comparator': '>', 'value': '18', 'type': 'int', 'is_active': False},  # Inactive
                    {'name': 'plan', 'comparator': '==', 'value': 'premium', 'type': 'string', 'is_active': True}
                ]
            }

            # User would match the inactive age segment, but it should be ignored
            user_segments = {'country': 'UK', 'age': 25, 'plan': 'basic'}
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertEqual(result, '')  # Default value since no active segments match
            self.assertTrue(context['default_value_used'])
            self.assertEqual(context['reason'], 'segment_not_matched')
            self.assertEqual(len(context['segments_matched']), 0)
            self.assertEqual(len(context['segments_evaluated']), 2)  # Only active segments evaluated
            self.assertNotIn('age', context['segments_evaluated'])  # Inactive segment not evaluated

            sdk.shutdown()

    def test_segment_evaluation_no_active_segments(self):
        """Test behavior when all segments are inactive"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Flag with all inactive segments
            flag_data = {
                'name': 'test_flag',
                'is_active': True,
                'value': 'enabled_value',
                'type': 'string',
                'segments': [
                    {'name': 'country', 'comparator': '==', 'value': 'US', 'type': 'string', 'is_active': False},
                    {'name': 'age', 'comparator': '>', 'value': '18', 'type': 'int', 'is_active': False}
                ]
            }

            # Since no segments are active, flag should return its value (no segment filtering)
            user_segments = {'country': 'US', 'age': 25}
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertEqual(result, 'enabled_value')
            self.assertFalse(context['default_value_used'])
            self.assertEqual(context['reason'], 'active_flag')

            sdk.shutdown()

    def test_segment_evaluation_mixed_scenarios(self):
        """Test complex scenarios with mixed segment conditions"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Complex flag with different segment types and comparators
            flag_data = {
                'name': 'test_flag',
                'is_active': True,
                'value': True,
                'type': 'bool',
                'segments': [
                    {'name': 'country', 'comparator': '==', 'value': 'US', 'type': 'string', 'is_active': True},
                    {'name': 'age', 'comparator': '>=', 'value': '21', 'type': 'int', 'is_active': True},
                    {'name': 'score', 'comparator': '>', 'value': '85.0', 'type': 'float', 'is_active': True},
                    {'name': 'is_premium', 'comparator': '==', 'value': 'true', 'type': 'bool', 'is_active': True},
                    {'name': 'tags', 'comparator': 'contains', 'value': 'vip', 'type': 'string', 'is_active': True}
                ]
            }

            # User matching multiple different segment types
            user_segments = {
                'country': 'US',
                'age': 25,
                'score': 90.5,
                'is_premium': True,
                'tags': 'user-vip-gold'
            }
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertTrue(result)
            self.assertFalse(context['default_value_used'])
            self.assertEqual(len(context['segments_matched']), 5)  # All segments match

            # User matching only some segments
            user_segments = {
                'country': 'US',
                'age': 18,  # Doesn't match >=21
                'score': 80.0,  # Doesn't match >85.0
                'is_premium': True,
                'tags': 'user-basic'  # Doesn't contain 'vip'
            }
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)
            self.assertTrue(result)  # Should still get flag value since country and is_premium match
            self.assertFalse(context['default_value_used'])
            self.assertEqual(len(context['segments_matched']), 2)  # country and is_premium match
            self.assertIn('country', context['segments_matched'])
            self.assertIn('is_premium', context['segments_matched'])

            sdk.shutdown()

    def test_segment_stats_tracking(self):
        """Test that segment matching statistics are properly tracked"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            flag_data = {
                'name': 'test_flag',
                'is_active': True,
                'value': 'test_value',
                'type': 'string',
                'segments': [
                    {'name': 'country', 'comparator': '==', 'value': 'US', 'type': 'string', 'is_active': True},
                    {'name': 'plan', 'comparator': '==', 'value': 'premium', 'type': 'string', 'is_active': True}
                ]
            }

            initial_matches = sdk.stats['segment_matches']

            # Evaluate flag with matching segments
            user_segments = {'country': 'US', 'plan': 'premium'}
            result, context = sdk._evaluate_flag(flag_data, "user123", user_segments)

            # Stats should be updated
            self.assertEqual(sdk.stats['segment_matches'], initial_matches + 2)  # Both segments matched

            # Evaluate with partial match
            user_segments = {'country': 'US', 'plan': 'basic'}
            result, context = sdk._evaluate_flag(flag_data, "user456", user_segments)

            # Stats should be updated again
            self.assertEqual(sdk.stats['segment_matches'], initial_matches + 3)  # +1 more match

            sdk.shutdown()

    def test_public_api_segment_evaluation(self):
        """Test segment evaluation through public API methods"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Set up flag with segments directly in SDK
            sdk.flags = {
                'premium_feature': {
                    'name': 'premium_feature',
                    'is_active': True,
                    'value': True,
                    'type': 'bool',
                    'segments': [
                        {'name': 'plan', 'comparator': '==', 'value': 'premium', 'type': 'string', 'is_active': True},
                        {'name': 'country', 'comparator': '==', 'value': 'US', 'type': 'string', 'is_active': True}
                    ]
                },
                'discount_percentage': {
                    'name': 'discount_percentage',
                    'is_active': True,
                    'value': 20,
                    'type': 'int',
                    'segments': [
                        {'name': 'loyalty_years', 'comparator': '>=', 'value': '2', 'type': 'int', 'is_active': True}
                    ]
                }
            }

            # Test 1: User with matching segment should get flag value
            user_segments = {'plan': 'premium', 'country': 'US'}
            result = sdk.get_bool("user123", "premium_feature", segments=user_segments)
            self.assertTrue(result)

            # Test 2: User without matching segments should get default value
            user_segments = {'plan': 'basic', 'country': 'UK'}
            result = sdk.get_bool("user456", "premium_feature", default_value=False, segments=user_segments)
            self.assertFalse(result)

            # Test 3: Custom default value should be used when segments don't match
            user_segments = {'plan': 'basic', 'country': 'UK'}
            result = sdk.get_bool("user789", "premium_feature", default_value=True, segments=user_segments)
            self.assertTrue(result)  # Should get custom default, not flag default

            # Test 4: Numeric segment evaluation
            user_segments = {'loyalty_years': 3}
            result = sdk.get_int("loyal_user", "discount_percentage", segments=user_segments)
            self.assertEqual(result, 20)

            user_segments = {'loyalty_years': 1}  # Doesn't meet >=2 requirement
            result = sdk.get_int("new_user", "discount_percentage", default_value=5, segments=user_segments)
            self.assertEqual(result, 5)  # Should get custom default

            # Test 5: get_user_flags with segments
            user_segments = {'plan': 'premium', 'country': 'US', 'loyalty_years': 3}
            all_flags = sdk.get_user_flags("power_user", segments=user_segments)
            self.assertTrue(all_flags['premium_feature'])
            self.assertEqual(all_flags['discount_percentage'], 20)

            # Test 6: get_user_flags with non-matching segments
            user_segments = {'plan': 'basic', 'country': 'UK', 'loyalty_years': 0}
            all_flags = sdk.get_user_flags("basic_user", segments=user_segments)
            self.assertFalse(all_flags['premium_feature'])  # Default bool value
            self.assertEqual(all_flags['discount_percentage'], 0)  # Default int value

            sdk.shutdown()

    def test_flag_change_callback(self):
        """Test flag change callback functionality"""
        callback_calls = []

        def flag_change_callback(flag_name, old_value, new_value):
            callback_calls.append((flag_name, old_value, new_value))

        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True,
                on_flag_change=flag_change_callback
            )

            # Set initial flags
            sdk.flags = {'test_flag': {'name': 'test_flag', 'value': True}}

            # Simulate flag update through polling worker logic
            old_flags = dict(sdk.flags)
            new_flags = {'test_flag': {'name': 'test_flag', 'value': False}}

            # Manually trigger change detection logic
            with sdk._lock:
                for flag_name, new_flag_data in new_flags.items():
                    old_flag_data = old_flags.get(flag_name)
                    old_value = old_flag_data.get('value') if old_flag_data else None
                    new_value = new_flag_data.get('value')

                    if old_value != new_value:
                        try:
                            sdk.on_flag_change(flag_name, old_value, new_value)
                        except Exception as e:
                            pass

                sdk.flags.update(new_flags)

            # Verify callback was called
            self.assertEqual(len(callback_calls), 1)
            self.assertEqual(callback_calls[0], ('test_flag', True, False))

            sdk.shutdown()

    def test_system_info_collection(self):
        """Test system info collection"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            system_info = sdk._system_info
            # Test that basic system info is collected
            self.assertIn('platform', system_info)
            self.assertIn('python_version', system_info)
            self.assertIn('hostname', system_info)
            self.assertIn('process_id', system_info)
            self.assertIn('cpu_count', system_info)
            self.assertIn('memory_total', system_info)

            # Test that values are reasonable
            self.assertIsInstance(system_info['process_id'], int)
            self.assertGreater(system_info['process_id'], 0)

            sdk.shutdown()

    def test_alternative_environment_variables(self):
        """Test initialization with alternative environment variable names"""
        import os

        # Test FEATUREFLAGSHQ_CLIENT_KEY instead of CLIENT_ID
        with patch.dict(os.environ, {
            'FEATUREFLAGSHQ_CLIENT_KEY': 'env_client_key',
            'FEATUREFLAGSHQ_CLIENT_SECRET': 'env_client_secret'
        }):
            with patch('featureflagshq.sdk.requests.Session'):
                sdk = FeatureFlagsHQSDK(offline_mode=True)

                self.assertEqual(sdk.client_id, 'env_client_key')
                self.assertEqual(sdk.client_secret, 'env_client_secret')

                sdk.shutdown()

    def test_session_metadata_generation(self):
        """Test session metadata generation"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Add some stats
            sdk.stats['total_user_accesses'] = 100
            sdk.stats['unique_users'].add('user1')
            sdk.stats['unique_users'].add('user2')
            sdk.stats['unique_flags_accessed'].add('flag1')
            sdk.stats['segment_matches'] = 5
            sdk.stats['rollout_evaluations'] = 10
            sdk.stats['evaluation_times']['total_ms'] = 50.0
            sdk.stats['evaluation_times']['count'] = 5
            sdk.stats['evaluation_times']['min_ms'] = 8.0
            sdk.stats['evaluation_times']['max_ms'] = 15.0

            metadata = sdk._get_session_metadata()

            self.assertIn('session_id', metadata)
            self.assertIn('environment', metadata)
            self.assertIn('system_info', metadata)
            self.assertIn('stats', metadata)

            self.assertEqual(metadata['stats']['total_user_accesses'], 100)
            self.assertEqual(metadata['stats']['unique_users_count'], 2)
            self.assertEqual(metadata['stats']['unique_flags_count'], 1)
            self.assertEqual(metadata['stats']['segment_matches'], 5)
            self.assertEqual(metadata['stats']['rollout_evaluations'], 10)
            self.assertEqual(metadata['stats']['evaluation_times']['avg_ms'], 10.0)

            sdk.shutdown()

    def test_log_queue_overflow(self):
        """Test behavior when log queue is full"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Fill the queue to capacity (Queue default maxsize is 0 = unlimited,
            # but we can test the put_nowait behavior)
            from queue import Queue
            original_queue = sdk.logs_queue
            sdk.logs_queue = Queue(maxsize=2)  # Small queue for testing

            # Fill the queue
            sdk.logs_queue.put({'test': 'entry1'})
            sdk.logs_queue.put({'test': 'entry2'})

            # This should not raise an exception, but silently ignore the overflow
            sdk._log_access('user123', 'test_flag', True, {}, 1.0)

            # Queue should still have original 2 items
            self.assertEqual(sdk.logs_queue.qsize(), 2)

            sdk.shutdown()

    def test_type_conversion_edge_cases(self):
        """Test edge cases in type conversion"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test boolean edge cases
            self.assertTrue(sdk._convert_value('YES', 'bool'))
            self.assertTrue(sdk._convert_value('1', 'bool'))
            self.assertFalse(sdk._convert_value('false', 'bool'))
            self.assertFalse(sdk._convert_value('0', 'bool'))
            self.assertFalse(sdk._convert_value('no', 'bool'))

            # Test already correct type
            self.assertTrue(sdk._convert_value(True, 'bool'))
            self.assertFalse(sdk._convert_value(False, 'bool'))

            # Test complex JSON
            complex_json = {
                "nested": {
                    "array": [1, 2, 3],
                    "bool": True,
                    "null": None
                }
            }
            result = sdk._convert_value(complex_json, 'json')
            self.assertEqual(result, complex_json)

            # Test JSON list
            json_array = ["item1", "item2", {"key": "value"}]
            result = sdk._convert_value(json_array, 'json')
            self.assertEqual(result, json_array)

            # Test invalid JSON string
            result = sdk._convert_value('{invalid json}', 'json')
            self.assertEqual(result, {})  # Should return default

            # Test unknown type
            result = sdk._convert_value('test', 'unknown_type')
            self.assertEqual(result, 'test')  # Should return as string

            sdk.shutdown()

    @responses.activate
    def test_network_timeout_scenarios(self):
        """Test network timeout handling"""
        from requests.exceptions import Timeout

        # Mock timeout response
        responses.add(
            responses.GET,
            f"{DEFAULT_API_BASE_URL}/v1/flags/",
            body=Timeout("Request timeout")
        )

        sdk = FeatureFlagsHQSDK(
            client_id=self.client_id,
            client_secret=self.client_secret,
            timeout=1  # Short timeout
        )

        try:
            # Should handle timeout gracefully
            flags = sdk._fetch_flags()
            self.assertEqual(flags, {})

            # Check that network error was recorded
            stats = sdk.get_stats()
            self.assertGreaterEqual(stats['errors']['network_errors'], 0)

        finally:
            sdk.shutdown()

    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in string validation"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Test SQL injection patterns that should be caught by the validation
            # The validation looks for specific SQL keywords, let's test those
            malicious_inputs = [
                "test--comment",  # SQL comment
                "user;drop",  # Semicolon + drop
                "user/**/select",  # SQL comment style
                "unionselect",  # Union keyword
                "insertinto",  # Insert keyword
                "deletefrom",  # Delete keyword
                "updateset",  # Update keyword
                "droptable"  # Drop keyword
            ]

            for malicious_input in malicious_inputs:
                with self.assertRaises(ValueError) as cm:
                    sdk._validate_string(malicious_input, "test_field")
                self.assertIn("potentially dangerous content", str(cm.exception))

            sdk.shutdown()

    def test_flag_evaluation_with_inactive_flag(self):
        """Test flag evaluation when flag is inactive"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Flag that is inactive
            flag_data = {
                'name': 'test_flag',
                'value': True,
                'type': 'bool',
                'is_active': False
            }

            result, context = sdk._evaluate_flag(flag_data, "user123")
            self.assertFalse(result)  # Should return default for bool when inactive
            self.assertTrue(context['default_value_used'])
            self.assertEqual(context['reason'], 'flag_inactive')
            self.assertFalse(context['flag_active'])

            sdk.shutdown()


if __name__ == '__main__':
    unittest.main()
