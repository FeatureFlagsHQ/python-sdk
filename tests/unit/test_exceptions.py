"""
Unit tests for FeatureFlagsHQ SDK exceptions

Tests all custom exception classes and their behavior.
"""

import pytest
import time
from featureflagshq.exceptions import (
    FeatureFlagsHQError,
    FeatureFlagsHQAuthError,
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQConfigError,
    FeatureFlagsHQTimeoutError,
    SecureFeatureFlagsHQError
)


class TestExceptionHierarchy:
    """Test the exception class hierarchy and inheritance"""

    def test_base_exception(self):
        """Test base FeatureFlagsHQError exception"""
        error = FeatureFlagsHQError("Base error message")
        
        assert str(error) == "Base error message"
        assert isinstance(error, Exception)
        assert isinstance(error, FeatureFlagsHQError)

    def test_auth_error_inheritance(self):
        """Test FeatureFlagsHQAuthError inherits from base"""
        error = FeatureFlagsHQAuthError("Authentication failed")
        
        assert str(error) == "Authentication failed"
        assert isinstance(error, FeatureFlagsHQError)
        assert isinstance(error, FeatureFlagsHQAuthError)

    def test_network_error_inheritance(self):
        """Test FeatureFlagsHQNetworkError inherits from base"""
        error = FeatureFlagsHQNetworkError("Network connection failed")
        
        assert str(error) == "Network connection failed"
        assert isinstance(error, FeatureFlagsHQError)
        assert isinstance(error, FeatureFlagsHQNetworkError)

    def test_config_error_inheritance(self):
        """Test FeatureFlagsHQConfigError inherits from base"""
        error = FeatureFlagsHQConfigError("Invalid configuration")
        
        assert str(error) == "Invalid configuration"
        assert isinstance(error, FeatureFlagsHQError)
        assert isinstance(error, FeatureFlagsHQConfigError)

    def test_timeout_error_inheritance(self):
        """Test FeatureFlagsHQTimeoutError inherits from base"""
        error = FeatureFlagsHQTimeoutError("Request timeout")
        
        assert str(error) == "Request timeout"
        assert isinstance(error, FeatureFlagsHQError)
        assert isinstance(error, FeatureFlagsHQTimeoutError)


class TestSecureFeatureFlagsHQError:
    """Test the enhanced security error class"""

    def test_basic_secure_error(self):
        """Test basic SecureFeatureFlagsHQError functionality"""
        error = SecureFeatureFlagsHQError("Security issue detected")
        
        assert str(error) == "Security issue detected"
        assert isinstance(error, FeatureFlagsHQError)
        assert error.error_code is None
        assert error.context == {}
        assert error.security_impact is False
        assert isinstance(error.timestamp, float)

    def test_secure_error_with_context(self):
        """Test SecureFeatureFlagsHQError with additional context"""
        context = {
            "user_id": "test_user",
            "action": "flag_access",
            "ip_address": "192.168.1.1"
        }
        
        error = SecureFeatureFlagsHQError(
            message="Suspicious activity detected",
            error_code="SUSPICIOUS_ACTIVITY",
            context=context,
            security_impact=True
        )
        
        assert str(error) == "Suspicious activity detected"
        assert error.error_code == "SUSPICIOUS_ACTIVITY"
        assert error.context == context
        assert error.security_impact is True
        assert isinstance(error.timestamp, float)

    def test_secure_error_timestamp(self):
        """Test that timestamp is set correctly"""
        start_time = time.time()
        error = SecureFeatureFlagsHQError("Test error")
        end_time = time.time()
        
        assert start_time <= error.timestamp <= end_time

    def test_secure_error_context_defaults(self):
        """Test that context defaults to empty dict"""
        error = SecureFeatureFlagsHQError("Test error", context=None)
        assert error.context == {}
        
        error2 = SecureFeatureFlagsHQError("Test error")
        assert error2.context == {}


class TestExceptionRaising:
    """Test that exceptions can be raised and caught properly"""

    def test_raise_base_exception(self):
        """Test raising and catching base exception"""
        with pytest.raises(FeatureFlagsHQError) as exc_info:
            raise FeatureFlagsHQError("Test error")
        
        assert str(exc_info.value) == "Test error"

    def test_raise_specific_exceptions(self):
        """Test raising and catching specific exception types"""
        # Auth error
        with pytest.raises(FeatureFlagsHQAuthError) as exc_info:
            raise FeatureFlagsHQAuthError("Auth failed")
        assert str(exc_info.value) == "Auth failed"
        
        # Network error
        with pytest.raises(FeatureFlagsHQNetworkError) as exc_info:
            raise FeatureFlagsHQNetworkError("Network failed")
        assert str(exc_info.value) == "Network failed"
        
        # Config error
        with pytest.raises(FeatureFlagsHQConfigError) as exc_info:
            raise FeatureFlagsHQConfigError("Config invalid")
        assert str(exc_info.value) == "Config invalid"
        
        # Timeout error
        with pytest.raises(FeatureFlagsHQTimeoutError) as exc_info:
            raise FeatureFlagsHQTimeoutError("Timeout occurred")
        assert str(exc_info.value) == "Timeout occurred"

    def test_catch_specific_as_base(self):
        """Test that specific exceptions can be caught as base exception"""
        # Should be able to catch any specific exception as base
        with pytest.raises(FeatureFlagsHQError):
            raise FeatureFlagsHQAuthError("Auth error")
        
        with pytest.raises(FeatureFlagsHQError):
            raise FeatureFlagsHQNetworkError("Network error")
        
        with pytest.raises(FeatureFlagsHQError):
            raise FeatureFlagsHQConfigError("Config error")
        
        with pytest.raises(FeatureFlagsHQError):
            raise FeatureFlagsHQTimeoutError("Timeout error")

    def test_exception_chaining(self):
        """Test exception chaining with 'from' clause"""
        original_error = ValueError("Original error")
        
        with pytest.raises(FeatureFlagsHQError) as exc_info:
            try:
                raise original_error
            except ValueError as e:
                raise FeatureFlagsHQError("Wrapped error") from e
        
        assert str(exc_info.value) == "Wrapped error"
        assert exc_info.value.__cause__ is original_error


class TestExceptionMessages:
    """Test exception message formatting and content"""

    def test_empty_message(self):
        """Test exceptions with empty messages"""
        error = FeatureFlagsHQError("")
        assert str(error) == ""

    def test_none_message(self):
        """Test exceptions with None message"""
        # This should work without issues
        error = FeatureFlagsHQError(None)
        assert str(error) == "None"

    def test_long_message(self):
        """Test exceptions with very long messages"""
        long_message = "A" * 1000
        error = FeatureFlagsHQError(long_message)
        assert str(error) == long_message
        assert len(str(error)) == 1000

    def test_unicode_message(self):
        """Test exceptions with unicode characters"""
        unicode_message = "Error with unicode: 测试 🚀 ñoño"
        error = FeatureFlagsHQError(unicode_message)
        assert str(error) == unicode_message

    def test_formatted_message(self):
        """Test exceptions with formatted messages"""
        error = FeatureFlagsHQError(f"Error code: {404}, status: {'failed'}")
        assert "Error code: 404" in str(error)
        assert "status: failed" in str(error)