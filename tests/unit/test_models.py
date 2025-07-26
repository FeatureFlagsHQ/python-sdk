"""
Unit tests for FeatureFlagsHQ SDK models

Tests all model classes, utility functions, and data structures.
"""

import json
import time
import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timezone

from featureflagshq.models import (
    FeatureFlagsHQSegment,
    FeatureFlagsHQRollout,
    FeatureFlagsHQFlag,
    FeatureFlagsHQUserAccessLog,
    FeatureFlagsHQSystemMetadata,
    generate_featureflagshq_signature,
    validate_hmac_signature,
    measure_time,
    __version__,
    BRAND_NAME
)
from featureflagshq.exceptions import FeatureFlagsHQConfigError


class TestUtilityFunctions:
    """Test utility functions and helpers"""

    def test_generate_signature_with_timestamp(self):
        """Test HMAC signature generation with provided timestamp"""
        client_id = "test_client"
        client_secret = "test_secret"
        payload = '{"test": "data"}'
        timestamp = "1234567890"

        signature, returned_timestamp = generate_featureflagshq_signature(
            client_id, client_secret, payload, timestamp
        )

        assert signature is not None
        assert len(signature) > 0
        assert returned_timestamp == timestamp
        assert isinstance(signature, str)

    def test_generate_signature_auto_timestamp(self):
        """Test HMAC signature generation with auto-generated timestamp"""
        client_id = "test_client"
        client_secret = "test_secret"
        payload = '{"test": "data"}'

        signature, timestamp = generate_featureflagshq_signature(
            client_id, client_secret, payload
        )

        assert signature is not None
        assert len(signature) > 0
        assert timestamp is not None
        assert int(timestamp) > 0
        # Timestamp should be recent (within last 60 seconds)
        assert abs(int(timestamp) - time.time()) < 60

    def test_signature_consistency(self):
        """Test that same inputs produce same signature"""
        client_id = "test_client"
        client_secret = "test_secret"
        payload = '{"test": "data"}'
        timestamp = "1234567890"

        sig1, _ = generate_featureflagshq_signature(client_id, client_secret, payload, timestamp)
        sig2, _ = generate_featureflagshq_signature(client_id, client_secret, payload, timestamp)

        assert sig1 == sig2

    def test_measure_time_context_manager(self):
        """Test measure_time context manager"""
        with measure_time() as get_time:
            time.sleep(0.01)  # 10ms
            elapsed_ms = get_time()

        assert elapsed_ms >= 8  # At least 8ms (allowing for timing variance)
        assert elapsed_ms < 100  # But not too much


class TestFeatureFlagsHQSegment:
    """Test FeatureFlagsHQSegment model and matching logic"""

    def test_segment_creation(self):
        """Test basic segment creation"""
        segment = FeatureFlagsHQSegment(
            name="test_segment",
            type="string",
            comparator="==",
            value="test_value",
            is_active=True,
            created_at="2023-01-01T00:00:00Z"
        )

        assert segment.name == "test_segment"
        assert segment.type == "string"
        assert segment.comparator == "=="
        assert segment.value == "test_value"
        assert segment.is_active is True

    def test_string_equality_matching(self):
        """Test string equality segment matching"""
        segment = FeatureFlagsHQSegment(
            name="role", type="string", comparator="==", value="admin",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )

        assert segment.matches_segment("admin") is True
        assert segment.matches_segment("user") is False
        assert segment.matches_segment("ADMIN") is False  # Case sensitive

    def test_string_contains_matching(self):
        """Test string contains segment matching"""
        segment = FeatureFlagsHQSegment(
            name="email", type="string", comparator="contains", value="@company.com",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )

        assert segment.matches_segment("user@company.com") is True
        assert segment.matches_segment("admin@company.com") is True
        assert segment.matches_segment("user@other.com") is False

    def test_integer_comparisons(self):
        """Test integer comparison segment matching"""
        # Greater than
        gt_segment = FeatureFlagsHQSegment(
            name="age", type="int", comparator=">", value="18",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )
        assert gt_segment.matches_segment(25) is True
        assert gt_segment.matches_segment(15) is False
        assert gt_segment.matches_segment("30") is True  # String coercion

    def test_inactive_segment(self):
        """Test that inactive segments don't match"""
        segment = FeatureFlagsHQSegment(
            name="test", type="string", comparator="==", value="match",
            is_active=False, created_at="2023-01-01T00:00:00Z"
        )

        assert segment.matches_segment("match") is False


class TestFeatureFlagsHQRollout:
    """Test FeatureFlagsHQRollout model"""

    def test_rollout_creation(self):
        """Test basic rollout creation"""
        rollout = FeatureFlagsHQRollout(percentage=50, sticky=True)
        
        assert rollout.percentage == 50
        assert rollout.sticky is True

    def test_rollout_default_sticky(self):
        """Test rollout with default sticky value"""
        rollout = FeatureFlagsHQRollout(percentage=25)
        
        assert rollout.percentage == 25
        assert rollout.sticky is True  # Default value


class TestFeatureFlagsHQFlag:
    """Test FeatureFlagsHQFlag model and evaluation logic"""

    def test_flag_from_dict_complete(self):
        """Test flag creation from complete dictionary"""
        flag_data = {
            "name": "test_flag",
            "type": "bool",
            "value": "true",
            "is_active": True,
            "created_at": "2023-01-01T00:00:00Z",
            "segments": [{
                "name": "premium",
                "type": "bool",
                "comparator": "==",
                "value": "true",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00Z"
            }],
            "rollout": {"percentage": 50, "sticky": True},
            "updated_at": "2023-01-02T00:00:00Z",
            "version": 2
        }

        flag = FeatureFlagsHQFlag.from_dict(flag_data)
        
        assert flag.name == "test_flag"
        assert flag.type == "bool"
        assert flag.value == "true"
        assert flag.is_active is True
        assert len(flag.segments) == 1
        assert flag.rollout.percentage == 50
        assert flag.updated_at == "2023-01-02T00:00:00Z"
        assert flag.version == 2

    def test_flag_from_dict_minimal(self):
        """Test flag creation from minimal dictionary"""
        minimal_data = {
            "name": "minimal_flag",
            "type": "string",
            "value": "default"
        }

        flag = FeatureFlagsHQFlag.from_dict(minimal_data)
        
        assert flag.name == "minimal_flag"
        assert flag.type == "string"
        assert flag.value == "default"
        assert flag.is_active is True  # Default
        assert flag.segments is None
        assert flag.rollout.percentage == 100  # Default
        assert flag.version == 1  # Default

    def test_flag_from_dict_missing_required(self):
        """Test flag creation with missing required fields"""
        with pytest.raises(FeatureFlagsHQConfigError):
            FeatureFlagsHQFlag.from_dict({"type": "string", "value": "test"})  # Missing name

        with pytest.raises(FeatureFlagsHQConfigError):
            FeatureFlagsHQFlag.from_dict({"name": "test", "value": "test"})  # Missing type

        with pytest.raises(FeatureFlagsHQConfigError):
            FeatureFlagsHQFlag.from_dict({"name": "test", "type": "string"})  # Missing value

    def test_flag_evaluation_active_full_rollout(self):
        """Test flag evaluation for active flag with full rollout"""
        flag = FeatureFlagsHQFlag(
            name="test_flag", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )

        result, context = flag.evaluate_for_user("user123")
        
        assert result is True
        assert context['flag_active'] is True
        assert context['rollout_qualified'] is True
        assert context['evaluation_reason'] == 'full_rollout'
        assert 'evaluation_time_ms' in context

    def test_flag_evaluation_inactive(self):
        """Test flag evaluation for inactive flag"""
        flag = FeatureFlagsHQFlag(
            name="test_flag", type="bool", value="true", is_active=False,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )

        result, context = flag.evaluate_for_user("user123")
        
        assert result is False  # Default bool value
        assert context['flag_active'] is False
        assert context['default_value_used'] is True
        assert context['evaluation_reason'] == 'flag_inactive'

    def test_flag_evaluation_with_segments_matching(self):
        """Test flag evaluation with matching segments"""
        segments = [FeatureFlagsHQSegment(
            name="premium", type="bool", comparator="==", value="true",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )]

        flag = FeatureFlagsHQFlag(
            name="premium_flag", type="string", value="premium_feature",
            is_active=True, created_at="2023-01-01T00:00:00Z",
            segments=segments, rollout=FeatureFlagsHQRollout(percentage=100)
        )

        result, context = flag.evaluate_for_user("user123", {"premium": True})
        
        assert result == "premium_feature"
        assert "premium" in context['segments_matched']
        assert "premium" in context['segments_evaluated']

    def test_flag_evaluation_segments_required_not_provided(self):
        """Test flag evaluation when segments are required but not provided"""
        segments = [FeatureFlagsHQSegment(
            name="premium", type="bool", comparator="==", value="true",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )]

        flag = FeatureFlagsHQFlag(
            name="premium_flag", type="string", value="premium_feature",
            is_active=True, created_at="2023-01-01T00:00:00Z",
            segments=segments, rollout=FeatureFlagsHQRollout(percentage=100)
        )

        result, context = flag.evaluate_for_user("user123")  # No segments provided
        
        assert result == ""  # Default string value
        assert context['default_value_used'] is True
        assert context['evaluation_reason'] == 'segments_required_but_not_provided'

    def test_flag_type_conversions_boolean(self):
        """Test flag boolean type conversions"""
        flag = FeatureFlagsHQFlag(
            name="bool_flag", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )

        # Test various boolean string values
        test_values = [
            ("true", True), ("false", False), ("yes", True), ("no", False),
            ("on", True), ("off", False), ("1", True), ("0", False),
            ("TRUE", True), ("FALSE", False), ("invalid", False)
        ]

        for value, expected in test_values:
            flag.value = value
            assert flag._get_typed_value() == expected

    def test_flag_type_conversions_integer(self):
        """Test flag integer type conversions"""
        flag = FeatureFlagsHQFlag(
            name="int_flag", type="int", value="42", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )

        assert flag._get_typed_value() == 42

        # Float string should truncate
        flag.value = "42.7"
        assert flag._get_typed_value() == 42

        # Invalid integer should return default
        flag.value = "invalid"
        assert flag._get_typed_value() == 0

    def test_flag_type_conversions_json(self):
        """Test flag JSON type conversions"""
        flag = FeatureFlagsHQFlag(
            name="json_flag", type="json", value='{"key": "value"}', is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )

        assert flag._get_typed_value() == {"key": "value"}

        # Invalid JSON should return default
        flag.value = "invalid json{"
        assert flag._get_typed_value() == {}

    def test_flag_default_values_by_type(self):
        """Test default values returned by type"""
        flag = FeatureFlagsHQFlag(
            name="test", type="bool", value="", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )

        assert flag._get_typed_default_value() is False

        flag.type = "int"
        assert flag._get_typed_default_value() == 0

        flag.type = "float"
        assert flag._get_typed_default_value() == 0.0

        flag.type = "json"
        assert flag._get_typed_default_value() == {}

        flag.type = "string"
        assert flag._get_typed_default_value() == ""


class TestFeatureFlagsHQUserAccessLog:
    """Test FeatureFlagsHQUserAccessLog model"""

    def test_user_access_log_creation(self):
        """Test basic user access log creation"""
        log = FeatureFlagsHQUserAccessLog(
            user_id="user123",
            flag_key="test_flag",
            flag_value=True,
            flag_type="bool",
            segments={"premium": True},
            evaluation_context={"test": "context"},
            evaluation_time_ms=1.5,
            timestamp="2023-01-01T00:00:00Z",
            session_id="session123",
            request_id="req123"
        )

        assert log.user_id == "user123"
        assert log.flag_key == "test_flag"
        assert log.flag_value is True
        assert log.flag_type == "bool"
        assert log.segments == {"premium": True}

    def test_user_access_log_auto_request_id(self):
        """Test automatic request ID generation"""
        log = FeatureFlagsHQUserAccessLog(
            user_id="user123",
            flag_key="test_flag",
            flag_value=True,
            flag_type="bool",
            segments=None,
            evaluation_context={},
            evaluation_time_ms=1.0,
            timestamp="2023-01-01T00:00:00Z",
            session_id="session123",
            request_id=""  # Empty request ID
        )

        # Should auto-generate request ID
        assert log.request_id is not None
        assert len(log.request_id) > 0
        assert len(log.request_id) == 16  # Based on implementation


class TestFeatureFlagsHQSystemMetadata:
    """Test FeatureFlagsHQSystemMetadata model"""

    @patch('featureflagshq.models.psutil')
    @patch('featureflagshq.models.platform')
    @patch('featureflagshq.models.os')
    def test_system_metadata_collection_with_psutil(self, mock_os, mock_platform, mock_psutil):
        """Test system metadata collection when psutil is available"""
        # Mock platform
        mock_platform.platform.return_value = "Linux-5.4.0-test"
        mock_platform.python_version.return_value = "3.9.7"
        mock_platform.node.return_value = "test-host"

        # Mock os
        mock_os.getpid.return_value = 12345

        # Mock psutil
        mock_psutil.cpu_count.return_value = 8
        mock_memory = Mock()
        mock_memory.total = 16777216000  # 16GB
        mock_psutil.virtual_memory.return_value = mock_memory

        metadata = FeatureFlagsHQSystemMetadata.collect()

        assert metadata.platform == "Linux-5.4.0-test"
        assert metadata.python_version == "3.9.7"
        assert metadata.cpu_count == 8
        assert metadata.memory_total == 16777216000
        assert metadata.hostname == "test-host"
        assert metadata.process_id == 12345
        assert metadata.sdk_version == __version__


class TestConstants:
    """Test module constants and metadata"""

    def test_version_constant(self):
        """Test that version constant is defined and valid"""
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_brand_name_constant(self):
        """Test that brand name constant is defined"""
        assert BRAND_NAME is not None
        assert isinstance(BRAND_NAME, str)
        assert BRAND_NAME == "FeatureFlagsHQ"