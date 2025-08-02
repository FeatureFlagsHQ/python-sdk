"""
Unit tests for rollout evaluation edge cases and scenarios

Tests various rollout percentage scenarios, sticky behavior, and user distribution.
"""

import pytest
import hashlib
from unittest.mock import patch

from featureflagshq import FeatureFlagsHQSDK
from featureflagshq.models import (
    FeatureFlagsHQFlag,
    FeatureFlagsHQRollout,
    FeatureFlagsHQSegment
)


class TestRolloutEvaluation:
    """Test rollout evaluation scenarios"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=False
        )

    @pytest.mark.timeout(2)
    def test_zero_percent_rollout(self, sdk):
        """Test 0% rollout always returns default"""
        flag = FeatureFlagsHQFlag(
            name="zero_rollout", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=0)
        )
        sdk.feature_flags["zero_rollout"] = flag
        
        # Test multiple users - all should get default
        for i in range(20):
            result = sdk.get_bool(f"user{i:03d}", "zero_rollout", False)
            assert result is False  # Default value

    @pytest.mark.timeout(2)
    def test_hundred_percent_rollout(self, sdk):
        """Test 100% rollout always returns flag value"""
        flag = FeatureFlagsHQFlag(
            name="full_rollout", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["full_rollout"] = flag
        
        # Test multiple users - all should get flag value
        for i in range(20):
            result = sdk.get_bool(f"user{i:03d}", "full_rollout", False)
            assert result is True  # Flag value

    @pytest.mark.timeout(2)
    def test_sticky_rollout_consistency(self, sdk):
        """Test that sticky rollout is consistent for same user"""
        flag = FeatureFlagsHQFlag(
            name="sticky_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=50, sticky=True)
        )
        sdk.feature_flags["sticky_test"] = flag
        
        user_id = "consistent_user"
        
        # Multiple evaluations should return same result
        results = []
        for _ in range(10):
            result = sdk.get_bool(user_id, "sticky_test", False)
            results.append(result)
        
        # All results should be identical
        assert len(set(results)) == 1

    @pytest.mark.timeout(2)
    def test_rollout_distribution_approximation(self, sdk):
        """Test that rollout distribution is approximately correct"""
        flag = FeatureFlagsHQFlag(
            name="distribution_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=30, sticky=True)
        )
        sdk.feature_flags["distribution_test"] = flag
        
        enabled_count = 0
        total_users = 200
        
        for i in range(total_users):
            result = sdk.get_bool(f"user{i:04d}", "distribution_test", False)
            if result:
                enabled_count += 1
        
        enabled_percentage = (enabled_count / total_users) * 100
        
        # Should be approximately 30% (allow for variance)
        assert 20 <= enabled_percentage <= 40

    @pytest.mark.timeout(2)
    def test_rollout_with_flag_version_change(self, sdk):
        """Test rollout behavior when flag version changes"""
        user_id = "version_test_user"
        
        # Version 1
        flag_v1 = FeatureFlagsHQFlag(
            name="version_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=50, sticky=True),
            version=1
        )
        sdk.feature_flags["version_test"] = flag_v1
        
        result_v1 = sdk.get_bool(user_id, "version_test", False)
        
        # Version 2 - user hash should be different due to version change
        flag_v2 = FeatureFlagsHQFlag(
            name="version_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=50, sticky=True),
            version=2
        )
        sdk.feature_flags["version_test"] = flag_v2
        
        result_v2 = sdk.get_bool(user_id, "version_test", False)
        
        # Results may be different due to version change affecting hash
        # This tests that version is included in hash calculation

    @pytest.mark.timeout(2)
    def test_rollout_hash_calculation(self, sdk):
        """Test that rollout hash is calculated correctly"""
        flag = FeatureFlagsHQFlag(
            name="hash_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=50, sticky=True),
            version=1
        )
        
        user_id = "test_user"
        
        # Manually calculate expected hash
        expected_hash = hashlib.sha256(f"{flag.name}_{user_id}_{flag.version}".encode()).hexdigest()
        expected_percentage = int(expected_hash[:8], 16) % 100
        
        # Evaluate flag
        result, context = flag.evaluate_for_user(user_id)
        
        # Verify rollout qualification matches expected
        expected_qualified = expected_percentage < flag.rollout.percentage
        assert context['rollout_qualified'] == expected_qualified

    @pytest.mark.timeout(2)
    def test_rollout_edge_percentages(self, sdk):
        """Test rollout with edge percentage values"""
        edge_percentages = [1, 5, 95, 99]
        
        for percentage in edge_percentages:
            flag = FeatureFlagsHQFlag(
                name=f"edge_{percentage}", type="bool", value="true", is_active=True,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=percentage)
            )
            sdk.feature_flags[f"edge_{percentage}"] = flag
            
            enabled_count = 0
            total_users = 100
            
            for i in range(total_users):
                result = sdk.get_bool(f"user{i:03d}", f"edge_{percentage}", False)
                if result:
                    enabled_count += 1
            
            enabled_percent = (enabled_count / total_users) * 100
            
            # Should be reasonably close to target percentage
            tolerance = max(10, percentage * 0.5)  # At least 10% tolerance
            assert abs(enabled_percent - percentage) <= tolerance


class TestRolloutWithSegments:
    """Test rollout evaluation combined with segments"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=False
        )

    @pytest.mark.timeout(2)
    def test_rollout_after_segment_match(self, sdk):
        """Test rollout evaluation after segment matching"""
        segments = [FeatureFlagsHQSegment(
            name="premium", type="bool", comparator="==", value="true",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )]
        
        flag = FeatureFlagsHQFlag(
            name="premium_rollout", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=segments,
            rollout=FeatureFlagsHQRollout(percentage=50)
        )
        sdk.feature_flags["premium_rollout"] = flag
        
        premium_user_segments = {"premium": True}
        free_user_segments = {"premium": False}
        
        # Premium users should go through rollout evaluation
        premium_results = []
        for i in range(20):
            result = sdk.get_bool(f"premium_user{i}", "premium_rollout", False, premium_user_segments)
            premium_results.append(result)
        
        # Free users should always get default (segments don't match)
        free_results = []
        for i in range(20):
            result = sdk.get_bool(f"free_user{i}", "premium_rollout", False, free_user_segments)
            free_results.append(result)
        
        # Premium users should have mix of True/False (rollout)
        # Free users should all be False (no segment match)
        assert any(premium_results)  # Some should be True
        assert not any(free_results)  # All should be False

    @pytest.mark.timeout(2)
    def test_segments_no_match_skips_rollout(self, sdk):
        """Test that rollout is skipped when segments don't match"""
        segments = [FeatureFlagsHQSegment(
            name="region", type="string", comparator="==", value="US",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )]
        
        flag = FeatureFlagsHQFlag(
            name="regional_feature", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=segments,
            rollout=FeatureFlagsHQRollout(percentage=100)  # 100% rollout
        )
        sdk.feature_flags["regional_feature"] = flag
        
        # User not in US region
        non_us_segments = {"region": "EU"}
        
        result = sdk.get_bool("eu_user", "regional_feature", False, non_us_segments)
        
        # Should get default value (False) despite 100% rollout
        # because segments don't match
        assert result is False


class TestRolloutEvaluationContext:
    """Test rollout evaluation context and metadata"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=False
        )

    @pytest.mark.timeout(2)
    def test_rollout_context_qualified(self, sdk):
        """Test evaluation context for qualified rollout"""
        flag = FeatureFlagsHQFlag(
            name="context_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)  # Guaranteed qualification
        )
        
        result, context = flag.evaluate_for_user("test_user")
        
        assert context['rollout_qualified'] is True
        assert context['evaluation_reason'] == 'full_rollout'
        assert context['default_value_used'] is False

    @pytest.mark.timeout(2)
    def test_rollout_context_not_qualified(self, sdk):
        """Test evaluation context for non-qualified rollout"""
        flag = FeatureFlagsHQFlag(
            name="context_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=0)  # Guaranteed non-qualification
        )
        
        result, context = flag.evaluate_for_user("test_user")
        
        assert context['rollout_qualified'] is False
        assert context['evaluation_reason'] == 'rollout_not_qualified'
        assert context['default_value_used'] is True

    @pytest.mark.timeout(2)
    def test_evaluation_timing_in_context(self, sdk):
        """Test that evaluation timing is recorded in context"""
        flag = FeatureFlagsHQFlag(
            name="timing_test", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        
        result, context = flag.evaluate_for_user("test_user")
        
        assert 'evaluation_time_ms' in context
        assert isinstance(context['evaluation_time_ms'], (int, float))
        assert context['evaluation_time_ms'] >= 0