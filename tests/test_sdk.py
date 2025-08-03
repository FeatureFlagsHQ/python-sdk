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
                offline_mode=True
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
