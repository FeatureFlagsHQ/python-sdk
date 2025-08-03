"""
Integration tests for FeatureFlagsHQ SDK

These tests verify the SDK works correctly in realistic scenarios
and integrates properly with external dependencies.
"""

import json
import time
import threading
from unittest.mock import patch, Mock
from queue import Queue

import pytest
import responses

from featureflagshq import FeatureFlagsHQSDK, create_client
from featureflagshq.models import FeatureFlagsHQFlag, FeatureFlagsHQSegment, FeatureFlagsHQRollout
from featureflagshq.exceptions import (
    FeatureFlagsHQAuthError,
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQTimeoutError
)


@pytest.mark.integration
class TestCompleteWorkflows:
    """Test complete SDK workflows and scenarios"""

    @pytest.mark.timeout(5)
    @responses.activate
    def test_end_to_end_flag_evaluation(self):
        """Test complete end-to-end flag evaluation workflow"""
        # Mock API responses
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={
                "data": [
                    {
                        "name": "premium_feature",
                        "type": "json",
                        "value": '{"feature": "enabled", "level": "premium"}',
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00Z",
                        "segments": [
                            {
                                "name": "subscription",
                                "type": "string",
                                "comparator": "==",
                                "value": "premium",
                                "is_active": True,
                                "created_at": "2023-01-01T00:00:00Z"
                            }
                        ],
                        "rollout": {"percentage": 100, "sticky": True},
                        "version": 1
                    }
                ],
                "environment": {"name": "production"}
            },
            status=200
        )

        responses.add(
            responses.POST,
            'https://api.featureflagshq.com/v1/logs/batch/',
            json={"status": "success"},
            status=200
        )

        # Create SDK and test workflow
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            polling_interval=60,  # Short for testing
            log_upload_interval=30,
            enable_metrics=True
        )

        try:
            # Wait for initial flag fetch
            time.sleep(0.1)

            # Test with matching segments
            user_segments = {"subscription": "premium"}
            result = sdk.get_json("user123", "premium_feature", {}, user_segments)
            expected = {"feature": "enabled", "level": "premium"}
            assert result == expected

            # Test with non-matching segments
            user_segments_no_match = {"subscription": "free"}
            result_no_match = sdk.get_json("user456", "premium_feature", {"default": True}, user_segments_no_match)
            assert result_no_match == {"default": True}

            # Test stats collection
            stats = sdk.get_stats()
            assert stats['total_user_accesses'] >= 2

        finally:
            sdk.shutdown()

    @pytest.mark.timeout(3)
    def test_rollout_percentage_distribution(self):
        """Test rollout percentage distribution with multiple users"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

        try:
            # Manually add the flag (since we're in offline mode)
            rollout_flag = FeatureFlagsHQFlag(
                name="rollout_test", type="bool", value="true", is_active=True,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=50, sticky=True)
            )
            sdk.feature_flags["rollout_test"] = rollout_flag

            # Test with multiple users
            enabled_count = 0
            total_users = 100

            for i in range(total_users):
                result = sdk.get_bool(f"user{i:03d}", "rollout_test", False)
                if result:
                    enabled_count += 1

            # Should be roughly 50% (allow for variance)
            assert 30 <= enabled_count <= 70  # 50% ± 20%

            # Same user should get consistent results (sticky behavior)
            user_id = "consistent_user"
            results = [sdk.get_bool(user_id, "rollout_test", False) for _ in range(5)]
            assert len(set(results)) == 1  # All results should be the same

        finally:
            sdk.shutdown()

    @pytest.mark.timeout(15)
    def test_concurrent_access_safety(self):
        """Test thread safety with concurrent access"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=True
        )

        try:
            # Add test flag
            test_flag = FeatureFlagsHQFlag(
                name="concurrent_flag", type="int", value="42", is_active=True,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=100)
            )
            sdk.feature_flags["concurrent_flag"] = test_flag

            results = []
            errors = []

            def worker(worker_id):
                try:
                    for i in range(10):  # Reduced iterations for faster testing
                        result = sdk.get_int(f"user_{worker_id}_{i}", "concurrent_flag", 0)
                        results.append(result)
                        time.sleep(0.001)  # Small delay to encourage race conditions
                except Exception as e:
                    errors.append(e)

            # Create and start threads
            threads = []
            for i in range(3):  # Reduced thread count
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join(timeout=10)
                if thread.is_alive():
                    pytest.fail("Thread did not complete within timeout")

            # Verify results
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(results) == 30  # 3 threads * 10 calls
            assert all(result == 42 for result in results)

        finally:
            sdk.shutdown()

    @pytest.mark.timeout(5)
    @responses.activate
    def test_api_error_handling_and_recovery(self):
        """Test API error handling and recovery mechanisms"""
        # Initially return error
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={"error": "Server error"},
            status=500
        )

        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            polling_interval=60
        )

        try:
            # Should handle initial error gracefully
            time.sleep(0.1)

            # SDK should still work with default values
            result = sdk.get_bool("user123", "nonexistent_flag", True)
            assert result is True

            # Clear responses and add successful response
            responses.reset()
            responses.add(
                responses.GET,
                'https://api.featureflagshq.com/v1/flags/',
                json={
                    "data": [
                        {
                            "name": "recovery_flag",
                            "type": "bool",
                            "value": "true",
                            "is_active": True,
                            "created_at": "2023-01-01T00:00:00Z",
                            "segments": [],
                            "rollout": {"percentage": 100, "sticky": True}
                        }
                    ]
                },
                status=200
            )

            # Manual refresh should work
            success = sdk.refresh_flags()
            assert success is True

            # Should now have the new flag
            result = sdk.get_bool("user123", "recovery_flag", False)
            assert result is True

        finally:
            sdk.shutdown()


@pytest.mark.integration 
class TestComplexScenarios:
    """Test complex real-world scenarios"""

    @pytest.mark.timeout(3)
    def test_ab_testing_scenario(self):
        """Test A/B testing scenario with multiple variants"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

        try:
            # Create A/B test flag
            variant_flag = FeatureFlagsHQFlag(
                name="ui_variant", type="string", value="variant_a", is_active=True,
                created_at="2023-01-01T00:00:00Z",
                segments=[FeatureFlagsHQSegment(
                    name="test_group", type="string", comparator="==", value="A",
                    is_active=True, created_at="2023-01-01T00:00:00Z"
                )],
                rollout=FeatureFlagsHQRollout(percentage=100)
            )

            sdk.feature_flags["ui_variant"] = variant_flag

            # Test users in different groups
            user_a_segments = {"test_group": "A"}
            user_b_segments = {"test_group": "B"}
            user_control_segments = {"test_group": "control"}

            variant_a = sdk.get_string("user_a", "ui_variant", "control", user_a_segments)
            variant_b = sdk.get_string("user_b", "ui_variant", "control", user_b_segments)
            variant_control = sdk.get_string("user_c", "ui_variant", "control", user_control_segments)

            assert variant_a == "variant_a"
            assert variant_b == "control"  # No matching segment
            assert variant_control == "control"  # No matching segment

        finally:
            sdk.shutdown()

    @pytest.mark.timeout(3)
    def test_geographic_targeting_scenario(self):
        """Test geographic targeting scenario"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

        try:
            # Create region-specific feature
            us_feature = FeatureFlagsHQFlag(
                name="regional_feature", type="json", 
                value='{"region": "US", "currency": "USD", "language": "en"}',
                is_active=True, created_at="2023-01-01T00:00:00Z",
                segments=[FeatureFlagsHQSegment(
                    name="country", type="string", comparator="==", value="US",
                    is_active=True, created_at="2023-01-01T00:00:00Z"
                )],
                rollout=FeatureFlagsHQRollout(percentage=100)
            )

            sdk.feature_flags["regional_feature"] = us_feature

            # Test users from different regions
            us_user_segments = {"country": "US", "region": "us-west"}
            eu_user_segments = {"country": "DE", "region": "eu-central"}

            default_config = {"region": "global", "currency": "USD", "language": "en"}

            us_config = sdk.get_json("us_user", "regional_feature", default_config, us_user_segments)
            eu_config = sdk.get_json("eu_user", "regional_feature", default_config, eu_user_segments)

            # US user should get US-specific config
            assert us_config["region"] == "US"
            assert us_config["currency"] == "USD"

            # EU user should get default
            assert eu_config["region"] == "global"

        finally:
            sdk.shutdown()


@pytest.mark.integration
class TestFactoryIntegration:
    """Test factory function integration"""

    @pytest.mark.timeout(3)
    def test_create_client_factory(self):
        """Test create_client factory function"""
        client = create_client(
            client_id="test_client",
            client_secret="test_secret",
            environment="staging",
            offline_mode=True,
            enable_metrics=False
        )

        try:
            assert isinstance(client, FeatureFlagsHQSDK)
            assert client.client_id == "test_client"
            assert client.environment == "staging"
            assert client.enable_metrics is False

            # Should work as expected
            result = client.get_bool("user123", "nonexistent", True)
            assert result is True

        finally:
            client.shutdown()

    @pytest.mark.timeout(3)
    def test_context_manager_integration(self):
        """Test context manager integration"""
        with create_client(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        ) as client:
            assert isinstance(client, FeatureFlagsHQSDK)
            
            # Should work within context
            result = client.get_bool("user123", "test_flag", True)
            assert result is True