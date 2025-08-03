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
            result = sdk._evaluate_flag(flag_data, "user123", segments)
            self.assertTrue(result)

            # Test segment not matching
            segments = {'country': 'UK'}
            result = sdk._evaluate_flag(flag_data, "user123", segments)
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

            result = sdk._evaluate_flag(flag_data, "user123")
            self.assertFalse(result)  # Should always return default with 0% rollout

            # Flag with 100% rollout
            flag_data['rollout']['percentage'] = 100
            result = sdk._evaluate_flag(flag_data, "user123")
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


if __name__ == '__main__':
    unittest.main()
