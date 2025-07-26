"""
Security-focused unit tests for FeatureFlagsHQ SDK

Tests all security features, input validation, sanitization,
rate limiting, and protection mechanisms.
"""

import time
import hmac
import hashlib
import base64
from unittest.mock import patch, Mock

import pytest

from featureflagshq import FeatureFlagsHQSDK
from featureflagshq.exceptions import FeatureFlagsHQError, FeatureFlagsHQConfigError
from featureflagshq.models import (
    generate_featureflagshq_signature,
    validate_hmac_signature
)


class TestHMACAuthentication:
    """Test HMAC signature generation and validation"""

    def test_signature_generation_consistency(self):
        """Test that signature generation is consistent"""
        client_id = "test_client"
        client_secret = "test_secret"
        payload = '{"test": "data"}'
        timestamp = "1234567890"

        sig1, _ = generate_featureflagshq_signature(client_id, client_secret, payload, timestamp)
        sig2, _ = generate_featureflagshq_signature(client_id, client_secret, payload, timestamp)

        assert sig1 == sig2
        assert len(sig1) > 0
        assert isinstance(sig1, str)

    def test_signature_uniqueness_across_inputs(self):
        """Test that different inputs produce different signatures"""
        client_id = "test_client"
        client_secret = "test_secret"
        timestamp = "1234567890"

        # Different payloads
        sig1, _ = generate_featureflagshq_signature(client_id, client_secret, '{"a": "1"}', timestamp)
        sig2, _ = generate_featureflagshq_signature(client_id, client_secret, '{"a": "2"}', timestamp)
        assert sig1 != sig2

        # Different client IDs
        sig3, _ = generate_featureflagshq_signature("different_client", client_secret, '{"a": "1"}', timestamp)
        assert sig1 != sig3

        # Different secrets
        sig4, _ = generate_featureflagshq_signature(client_id, "different_secret", '{"a": "1"}', timestamp)
        assert sig1 != sig4

        # Different timestamps
        sig5, _ = generate_featureflagshq_signature(client_id, client_secret, '{"a": "1"}', "9876543210")
        assert sig1 != sig5

    def test_signature_validation_success(self):
        """Test successful signature validation"""
        client_id = "test_client"
        client_secret = "test_secret"
        payload = '{"test": "data"}'
        timestamp = "1234567890"

        signature, _ = generate_featureflagshq_signature(client_id, client_secret, payload, timestamp)
        is_valid = validate_hmac_signature(client_id, client_secret, payload, timestamp, signature)

        assert is_valid is True

    def test_signature_validation_failure(self):
        """Test signature validation failure scenarios"""
        client_id = "test_client"
        client_secret = "test_secret"
        payload = '{"test": "data"}'
        timestamp = "1234567890"

        # Invalid signature
        is_valid = validate_hmac_signature(client_id, client_secret, payload, timestamp, "invalid_signature")
        assert is_valid is False

        # Tampered payload
        is_valid = validate_hmac_signature(client_id, client_secret, '{"test": "tampered"}', timestamp, "valid_sig")
        assert is_valid is False

        # Wrong secret
        is_valid = validate_hmac_signature(client_id, "wrong_secret", payload, timestamp, "valid_sig")
        assert is_valid is False

    def test_signature_validation_edge_cases(self):
        """Test signature validation with edge cases"""
        # None values
        assert validate_hmac_signature(None, None, None, None, None) is False

        # Empty strings
        assert validate_hmac_signature("", "", "", "", "") is False

        # Invalid timestamp format
        assert validate_hmac_signature("client", "secret", "payload", "invalid_ts", "sig") is False


class TestInputValidation:
    """Test input validation and sanitization"""

    @pytest.fixture
    def sdk(self):
        """Create SDK instance for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    def test_user_id_injection_protection(self, sdk):
        """Test protection against injection attacks in user IDs"""
        malicious_user_ids = [
            "user'; DROP TABLE users; --",
            "user<script>alert('xss')</script>",
            "user\x00with\x00nulls",
            "user\nwith\nnewlines",
            "user\r\nwith\r\ncarriage",
            "user\twith\ttabs",
            "user\x1b[0mwith\x1bansi",
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32"
        ]

        for malicious_id in malicious_user_ids:
            with pytest.raises(FeatureFlagsHQError):
                sdk.get(malicious_id, "test_flag", "default")

    def test_flag_key_injection_protection(self, sdk):
        """Test protection against injection attacks in flag keys"""
        malicious_flag_keys = [
            "flag'; DROP TABLE flags; --",
            "flag/../../secret",
            "flag\\..\\..\\secret",
            "flag<script>",
            "flag\x00null",
            "flag with spaces",
            "flag\nwith\nnewlines"
        ]

        for malicious_key in malicious_flag_keys:
            with pytest.raises(FeatureFlagsHQError):
                sdk.get("user123", malicious_key, "default")

    def test_user_id_length_limits(self, sdk):
        """Test user ID length validation"""
        # Valid length should work
        valid_user = "user_" + "a" * 250  # Under limit
        sdk._validate_user_id(valid_user)  # Should not raise

        # Excessive length should be rejected
        too_long_user = "user_" + "a" * 300  # Over limit
        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_user_id(too_long_user)

    def test_flag_key_length_limits(self, sdk):
        """Test flag key length validation"""
        # Valid length should work
        valid_flag = "flag_" + "a" * 120  # Under limit
        sdk._validate_flag_key(valid_flag)  # Should not raise

        # Excessive length should be rejected
        too_long_flag = "flag_" + "a" * 200  # Over limit
        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_flag_key(too_long_flag)

    def test_segments_sanitization(self, sdk):
        """Test user segments sanitization"""
        dangerous_segments = {
            "normal_key": "normal_value",
            "xss_attempt": "<script>alert('xss')</script>",
            "sql_injection": "'; DROP TABLE users; --",
            "null_bytes": "value\x00with\x00nulls",
            "newlines": "value\nwith\nnewlines",
            "long_value": "A" * 2000,  # Excessive length
            "": "empty_key",  # Empty key
            "unicode_attack": "test\u202e\u0040evil.com"
        }

        sanitized = sdk._sanitize_segments(dangerous_segments)

        # Should keep normal values
        assert sanitized.get("normal_key") == "normal_value"

        # Should remove dangerous keys
        assert "" not in sanitized

        # Should truncate long values
        if "long_value" in sanitized:
            assert len(sanitized["long_value"]) <= 1024

        # Should remove null bytes
        if "null_bytes" in sanitized:
            assert "\x00" not in sanitized["null_bytes"]

        # Should remove newlines
        if "newlines" in sanitized:
            assert "\n" not in sanitized["newlines"]


class TestRateLimiting:
    """Test rate limiting functionality"""

    @pytest.fixture
    def sdk(self):
        """Create SDK instance for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    def test_normal_usage_allowed(self, sdk):
        """Test that normal usage is allowed"""
        user_id = "normal_user"

        # Normal usage should be allowed
        for _ in range(10):
            assert sdk._rate_limit_check(user_id) is True

    def test_rate_limit_enforcement(self, sdk):
        """Test that rate limits are enforced"""
        user_id = "heavy_user"

        # Simulate heavy usage by directly setting rate limit state
        sdk._rate_limits[user_id] = (1001, time.time())  # Exceed limit

        # Should be rate limited
        assert sdk._rate_limit_check(user_id) is False

    def test_rate_limit_per_user(self, sdk):
        """Test that rate limits are applied per user"""
        user1 = "user1"
        user2 = "user2"

        # Limit user1
        sdk._rate_limits[user1] = (1001, time.time())

        # user1 should be limited, user2 should not
        assert sdk._rate_limit_check(user1) is False
        assert sdk._rate_limit_check(user2) is True