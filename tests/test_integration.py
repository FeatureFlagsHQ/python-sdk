import os
import time
import unittest
from unittest.mock import patch

import responses

from featureflagshq import FeatureFlagsHQSDK, DEFAULT_API_BASE_URL


class TestIntegration(unittest.TestCase):
    """Integration tests for FeatureFlagsHQ SDK"""

    def setUp(self):
        self.client_id = os.getenv('FEATUREFLAGSHQ_CLIENT_ID', 'test_client_id')
        self.client_secret = os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET', 'test_client_secret')
        self.environment = os.getenv('FEATUREFLAGSHQ_ENVIRONMENT', 'test')

    @unittest.skipUnless(
        os.getenv('FEATUREFLAGSHQ_INTEGRATION_TESTS'),
        "Integration tests require FEATUREFLAGSHQ_INTEGRATION_TESTS=1"
    )
    def test_real_api_integration(self):
        """Test real API integration (requires environment variables)"""
        sdk = FeatureFlagsHQSDK(
            client_id=self.client_id,
            client_secret=self.client_secret,
            environment=self.environment
        )

        try:
            # Wait for initialization
            time.sleep(2)

            # Test flag retrieval
            result = sdk.get_bool("integration_test_user", "test_flag", default_value=False)
            self.assertIsInstance(result, bool)

            # Test health check
            health = sdk.get_health_check()
            self.assertIn('status', health)

            # Test stats
            stats = sdk.get_stats()
            self.assertIn('total_user_accesses', stats)

        finally:
            sdk.shutdown()

    @responses.activate
    def test_end_to_end_flow(self):
        """Test complete end-to-end flow with mocked API"""
        # Mock initial flag fetch
        responses.add(
            responses.GET,
            f"{DEFAULT_API_BASE_URL}/v1/flags/",
            json={
                "data": [
                    {
                        "name": "welcome_message",
                        "value": "Hello, World!",
                        "type": "string",
                        "is_active": True
                    },
                    {
                        "name": "enable_dark_mode",
                        "value": True,
                        "type": "bool",
                        "is_active": True,
                        "rollout": {"percentage": 50}
                    },
                    {
                        "name": "max_items",
                        "value": 25,
                        "type": "int",
                        "is_active": True,
                        "segments": [
                            {
                                "name": "user_type",
                                "comparator": "==",
                                "value": "premium",
                                "type": "string"
                            }
                        ]
                    }
                ]
            },
            status=200
        )

        # Mock log upload
        responses.add(
            responses.POST,
            f"{DEFAULT_API_BASE_URL}/v1/logs/batch/",
            json={"status": "success"},
            status=200
        )

        # Create SDK
        sdk = FeatureFlagsHQSDK(
            client_id=self.client_id,
            client_secret=self.client_secret,
            environment=self.environment
        )

        try:
            # Wait for initialization
            time.sleep(0.5)

            # Test different flag types
            message = sdk.get_string("user123", "welcome_message", default_value="Default")
            self.assertEqual(message, "Hello, World!")

            # Test boolean flag
            dark_mode = sdk.get_bool("user123", "enable_dark_mode", default_value=False)
            self.assertIsInstance(dark_mode, bool)

            # Test integer flag with segments
            segments = {"user_type": "premium"}
            max_items = sdk.get_int("user123", "max_items", default_value=10, segments=segments)
            self.assertEqual(max_items, 25)

            # Test with different segments
            segments = {"user_type": "basic"}
            max_items = sdk.get_int("user123", "max_items", default_value=10, segments=segments)
            self.assertEqual(max_items, 10)  # Should use default

            # Test bulk flag retrieval
            user_flags = sdk.get_user_flags("user123", segments={"user_type": "premium"})
            self.assertIn("welcome_message", user_flags)
            self.assertIn("enable_dark_mode", user_flags)
            self.assertIn("max_items", user_flags)

            # Test stats after usage
            stats = sdk.get_stats()
            self.assertGreater(stats['total_user_accesses'], 0)
            self.assertGreater(stats['unique_users_count'], 0)

            # Test manual refresh
            success = sdk.refresh_flags()
            self.assertTrue(success)

            # Test health check
            health = sdk.get_health_check()
            self.assertEqual(health['status'], 'healthy')

        finally:
            sdk.shutdown()

    def test_error_handling_and_resilience(self):
        """Test error handling and resilience features"""
        with patch('featureflagshq.sdk.requests.Session') as mock_session:
            # Mock session to raise connection error
            mock_response = mock_session.return_value.get.return_value
            mock_response.raise_for_status.side_effect = Exception("Connection failed")

            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                environment=self.environment
            )

            try:
                # SDK should still work with defaults even if API fails
                result = sdk.get_bool("user123", "test_flag", default_value=True)
                self.assertTrue(result)

                # Check that errors are tracked
                stats = sdk.get_stats()
                self.assertGreaterEqual(stats['errors']['network_errors'], 0)

            finally:
                sdk.shutdown()

    def test_concurrent_usage(self):
        """Test SDK behavior under concurrent usage"""
        import threading
        import queue

        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            results = queue.Queue()

            def worker(worker_id):
                for i in range(10):
                    user_id = f"user_{worker_id}_{i}"
                    result = sdk.get_bool(user_id, "test_flag", default_value=True)
                    results.put((worker_id, i, result))

            # Start multiple threads
            threads = []
            for worker_id in range(5):
                thread = threading.Thread(target=worker, args=(worker_id,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Check that all requests completed
            result_count = 0
            while not results.empty():
                worker_id, i, result = results.get()
                self.assertIsInstance(result, bool)
                result_count += 1

            self.assertEqual(result_count, 50)  # 5 workers × 10 requests

            sdk.shutdown()

    def test_memory_usage_and_cleanup(self):
        """Test memory usage and cleanup behavior"""
        with patch('featureflagshq.sdk.requests.Session'):
            sdk = FeatureFlagsHQSDK(
                client_id=self.client_id,
                client_secret=self.client_secret,
                offline_mode=True
            )

            # Generate many unique users and flags to test cleanup
            for i in range(15000):  # Exceeds MAX_UNIQUE_USERS_TRACKED
                user_id = f"user_{i}"
                flag_name = "test_flag"
                sdk.get_bool(user_id, flag_name, default_value=True)

            # Check that cleanup occurred
            stats = sdk.get_stats()
            self.assertLessEqual(stats['unique_users_count'], 10000)  # MAX_UNIQUE_USERS_TRACKED

            sdk.shutdown()


if __name__ == '__main__':
    # Print setup instructions
    print("\nIntegration Test Setup:")
    print("=" * 50)
    print("To run integration tests against real API:")
    print("1. Set environment variables:")
    print("   export FEATUREFLAGSHQ_CLIENT_ID='your_client_id'")
    print("   export FEATUREFLAGSHQ_CLIENT_SECRET='your_client_secret'")
    print("   export FEATUREFLAGSHQ_ENVIRONMENT='test'")
    print("   export FEATUREFLAGSHQ_INTEGRATION_TESTS=1")
    print("2. Run: python -m pytest tests/test_integration.py -v")
    print("\nRunning offline tests only...\n")

    unittest.main()
