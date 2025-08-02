"""
Unit tests for edge cases and boundary conditions

Tests type conversions, malformed data handling, and boundary conditions.
"""

import json
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from featureflagshq import FeatureFlagsHQSDK
from featureflagshq.models import (
    FeatureFlagsHQFlag,
    FeatureFlagsHQSegment,
    FeatureFlagsHQRollout,
    FeatureFlagsHQUserAccessLog
)
from featureflagshq.exceptions import FeatureFlagsHQError, FeatureFlagsHQConfigError


class TestTypeConversions:
    """Test type conversion edge cases"""

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
    def test_get_bool_edge_cases(self, sdk):
        """Test boolean conversion edge cases"""
        flag = FeatureFlagsHQFlag(
            name="bool_flag", type="bool", value="", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["bool_flag"] = flag
        
        # Test various boolean-ish values
        test_cases = [
            ("true", True), ("false", False), ("TRUE", True), ("FALSE", False),
            ("yes", True), ("no", False), ("on", True), ("off", False),
            ("1", True), ("0", False), ("invalid", False), ("", False)
        ]
        
        for value, expected in test_cases:
            flag.value = value
            result = sdk.get_bool("user123", "bool_flag")
            assert result == expected

    @pytest.mark.timeout(2)
    def test_get_int_edge_cases(self, sdk):
        """Test integer conversion edge cases"""
        flag = FeatureFlagsHQFlag(
            name="int_flag", type="int", value="", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["int_flag"] = flag
        
        # Test various integer-ish values
        test_cases = [
            ("42", 42), ("42.7", 42), ("-15", -15), ("0", 0),
            ("invalid", 0), ("", 0), ("42.999", 42), ("1e3", 1000)
        ]
        
        for value, expected in test_cases:
            flag.value = value
            result = sdk.get_int("user123", "int_flag", default_value=0)
            assert result == expected

    @pytest.mark.timeout(2)
    def test_get_float_edge_cases(self, sdk):
        """Test float conversion edge cases"""
        flag = FeatureFlagsHQFlag(
            name="float_flag", type="float", value="", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["float_flag"] = flag
        
        # Test various float-ish values
        test_cases = [
            ("42.5", 42.5), ("42", 42.0), ("-15.7", -15.7), ("0.0", 0.0),
            ("invalid", 5.0), ("", 5.0), ("1e-3", 0.001)
        ]
        
        for value, expected in test_cases:
            flag.value = value
            result = sdk.get_float("user123", "float_flag", default_value=5.0)
            assert result == expected

    @pytest.mark.timeout(2)
    def test_get_json_edge_cases(self, sdk):
        """Test JSON parsing edge cases"""
        flag = FeatureFlagsHQFlag(
            name="json_flag", type="json", value="", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=100)
        )
        sdk.feature_flags["json_flag"] = flag
        
        # Test various JSON values
        test_cases = [
            ('{"key": "value"}', {"key": "value"}),
            ('[]', []),
            ('null', None),
            ('true', True),
            ('42', 42),
            ('invalid json{', {"default": True}),  # Malformed JSON
            ('', {"default": True})  # Empty string
        ]
        
        for value, expected in test_cases:
            flag.value = value
            result = sdk.get_json("user123", "json_flag", default_value={"default": True})
            assert result == expected


class TestMalformedDataHandling:
    """Test handling of malformed or unexpected data"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(2)
    def test_malformed_flag_data(self, sdk):
        """Test handling of malformed flag data"""
        malformed_data_cases = [
            {},  # Empty dict
            {"name": "test"},  # Missing required fields
            {"name": "test", "type": "bool"},  # Missing value
            {"name": "", "type": "bool", "value": "true"},  # Empty name
            {"name": None, "type": "bool", "value": "true"},  # None name
        ]
        
        for malformed_data in malformed_data_cases:
            with pytest.raises(FeatureFlagsHQConfigError):
                FeatureFlagsHQFlag.from_dict(malformed_data)

    @pytest.mark.timeout(2)
    def test_malformed_segment_data(self, sdk):
        """Test segment matching with malformed data"""
        segment = FeatureFlagsHQSegment(
            name="test_segment", type="int", comparator=">", value="not_a_number",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )
        
        # Should handle gracefully and return False
        assert segment.matches_segment(25) is False
        assert segment.matches_segment("not_a_number") is False

    @pytest.mark.timeout(2)
    def test_unknown_segment_comparator(self, sdk):
        """Test segment with unknown comparator"""
        segment = FeatureFlagsHQSegment(
            name="test_segment", type="string", comparator="unknown_op", value="test",
            is_active=True, created_at="2023-01-01T00:00:00Z"
        )
        
        # Should return False for unknown comparator
        assert segment.matches_segment("test") is False

    @pytest.mark.timeout(2)
    def test_none_values_in_methods(self, sdk):
        """Test methods with None values"""
        # Test get methods with None flag key
        with pytest.raises(FeatureFlagsHQError):
            sdk.get_bool("user123", None)
        
        # Test get methods with None user ID
        with pytest.raises(FeatureFlagsHQError):
            sdk.get_bool(None, "test_flag")


class TestBoundaryConditions:
    """Test boundary conditions and limits"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(2)
    def test_maximum_length_inputs(self, sdk):
        """Test maximum length inputs"""
        # Maximum valid user ID (at limit)
        max_user_id = "user_" + "a" * (sdk.MAX_USER_ID_LENGTH - 5)
        sdk._validate_user_id(max_user_id)  # Should not raise
        
        # Over maximum user ID
        over_max_user_id = "user_" + "a" * (sdk.MAX_USER_ID_LENGTH)
        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_user_id(over_max_user_id)
        
        # Maximum valid flag key
        max_flag_key = "flag_" + "a" * (sdk.MAX_FLAG_KEY_LENGTH - 5)
        sdk._validate_flag_key(max_flag_key)  # Should not raise
        
        # Over maximum flag key
        over_max_flag_key = "flag_" + "a" * (sdk.MAX_FLAG_KEY_LENGTH)
        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_flag_key(over_max_flag_key)

    @pytest.mark.timeout(2)
    def test_zero_and_negative_rollout_percentages(self, sdk):
        """Test rollout with edge percentage values"""
        # Zero percent rollout - should always use default
        zero_rollout_flag = FeatureFlagsHQFlag(
            name="zero_rollout", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=0)
        )
        sdk.feature_flags["zero_rollout"] = zero_rollout_flag
        
        # Should always return default (False) for 0% rollout
        results = [sdk.get_bool(f"user{i}", "zero_rollout") for i in range(10)]
        assert all(result is False for result in results)

    @pytest.mark.timeout(2)
    def test_large_segments_dictionary(self, sdk):
        """Test with large segments dictionary"""
        # Create large segments dictionary
        large_segments = {f"key_{i}": f"value_{i}" for i in range(100)}
        
        # Should handle gracefully
        sanitized = sdk._sanitize_segments(large_segments)
        assert isinstance(sanitized, dict)
        assert len(sanitized) <= len(large_segments)

    @pytest.mark.timeout(2)
    def test_empty_and_whitespace_strings(self, sdk):
        """Test empty and whitespace-only strings"""
        empty_strings = ["", "   ", "\t", "\n", "\r\n"]
        
        for empty_string in empty_strings:
            with pytest.raises(FeatureFlagsHQError):
                sdk._validate_user_id(empty_string)
            
            with pytest.raises(FeatureFlagsHQError):
                sdk._validate_flag_key(empty_string)


class TestSpecialCharacters:
    """Test handling of special characters and encodings"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(2)
    def test_unicode_handling(self, sdk):
        """Test Unicode character handling"""
        # These should be handled gracefully (possibly with warnings)
        unicode_inputs = [
            "user_测试",
            "user_🚀",
            "user_ñoño",
            "user_Москва"
        ]
        
        for unicode_input in unicode_inputs:
            try:
                # Some may pass validation, others may not, but shouldn't crash
                sdk._validate_user_id(unicode_input)
            except FeatureFlagsHQError:
                pass  # Expected for some Unicode characters

    @pytest.mark.timeout(2)
    def test_control_character_blocking(self, sdk):
        """Test that control characters are properly blocked"""
        control_chars = [
            "user\x00null",
            "user\x01control",
            "user\x08backspace",
            "user\x0cformfeed",
            "user\x1bescape"
        ]
        
        for control_input in control_chars:
            with pytest.raises(FeatureFlagsHQError):
                sdk._validate_user_id(control_input)


class TestUserAccessLogEdgeCases:
    """Test UserAccessLog edge cases"""

    @pytest.mark.timeout(2)
    def test_user_access_log_auto_generation(self):
        """Test auto-generation of request ID"""
        log1 = FeatureFlagsHQUserAccessLog(
            user_id="user123", flag_key="test_flag", flag_value=True,
            flag_type="bool", segments=None, evaluation_context={},
            evaluation_time_ms=1.0, timestamp="2023-01-01T00:00:00Z",
            session_id="session123", request_id=""
        )
        
        log2 = FeatureFlagsHQUserAccessLog(
            user_id="user456", flag_key="test_flag", flag_value=True,
            flag_type="bool", segments=None, evaluation_context={},
            evaluation_time_ms=1.0, timestamp="2023-01-01T00:00:00Z",
            session_id="session123", request_id=""
        )
        
        # Should auto-generate different request IDs
        assert log1.request_id != log2.request_id
        assert len(log1.request_id) == 16
        assert len(log2.request_id) == 16

    @pytest.mark.timeout(2)
    def test_segments_copy_safety(self):
        """Test that segments are safely copied"""
        original_segments = {"key": "value"}
        
        log = FeatureFlagsHQUserAccessLog(
            user_id="user123", flag_key="test_flag", flag_value=True,
            flag_type="bool", segments=original_segments, evaluation_context={},
            evaluation_time_ms=1.0, timestamp="2023-01-01T00:00:00Z",
            session_id="session123", request_id="req123"
        )
        
        # Modifying original should not affect log
        original_segments["key"] = "modified"
        assert log.segments["key"] == "value"