"""
Unit tests for FeatureFlagsHQ SDK main class

Tests the core SDK functionality, initialization, flag operations,
and all public methods.
"""

import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from queue import Queue

import pytest
import requests
from requests.exceptions import ConnectionError, Timeout

from featureflagshq import FeatureFlagsHQSDK, create_client
from featureflagshq.exceptions import (
    FeatureFlagsHQError,
    FeatureFlagsHQAuthError,
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQConfigError,
    FeatureFlagsHQTimeoutError
)
from featureflagshq.models import (
    FeatureFlagsHQFlag,
    FeatureFlagsHQSegment,
    FeatureFlagsHQRollout,
    __version__
)


class TestSDKInitialization:
    """Test SDK initialization and configuration"""

    def test_valid_initialization(self):
        """Test SDK initialization with valid parameters"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

        assert sdk.client_id == "test_client"
        assert sdk.client_secret == "test_secret"
        assert sdk.offline_mode is True
        assert sdk.enable_metrics is True  # Default
        assert sdk.environment == "production"  # Default
        sdk.shutdown()

    def test_initialization_with_custom_config(self):
        """Test SDK initialization with custom configuration"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            api_base_url="https://custom.api.com",
            environment="staging",
            polling_interval=600,
            timeout=60,
            enable_metrics=False,
            debug=True,
            offline_mode=True
        )

        assert sdk.api_base_url == "https://custom.api.com"
        assert sdk.environment == "staging"
        assert sdk.polling_interval == 600
        assert sdk.timeout == 60
        assert sdk.enable_metrics is False
        assert sdk.debug is True
        sdk.shutdown()

    def test_missing_credentials_error(self):
        """Test that missing credentials raise configuration error"""
        with pytest.raises(FeatureFlagsHQConfigError):
            FeatureFlagsHQSDK(client_id="", client_secret="")

        with pytest.raises(FeatureFlagsHQConfigError):
            FeatureFlagsHQSDK(client_id=None, client_secret=None)

    def test_invalid_polling_interval_error(self):
        """Test that invalid polling interval raises configuration error"""
        with pytest.raises(FeatureFlagsHQConfigError):
            FeatureFlagsHQSDK(
                client_id="test_client",
                client_secret="test_secret",
                polling_interval=10  # Less than minimum (30)
            )


class TestFlagOperations:
    """Test flag retrieval and evaluation operations"""

    @pytest.fixture
    def sdk_with_flags(self):
        """Create SDK with test flags"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=False  # Disable for cleaner tests
        )

        # Add test flags
        flags = {
            "bool_flag": FeatureFlagsHQFlag(
                name="bool_flag", type="bool", value="true", is_active=True,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=100)
            ),
            "string_flag": FeatureFlagsHQFlag(
                name="string_flag", type="string", value="test_value", is_active=True,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=100)
            ),
            "int_flag": FeatureFlagsHQFlag(
                name="int_flag", type="int", value="42", is_active=True,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=100)
            ),
            "inactive_flag": FeatureFlagsHQFlag(
                name="inactive_flag", type="bool", value="true", is_active=False,
                created_at="2023-01-01T00:00:00Z", segments=None,
                rollout=FeatureFlagsHQRollout(percentage=100)
            )
        }
        
        sdk.feature_flags.update(flags)
        yield sdk
        sdk.shutdown()

    def test_get_bool(self, sdk_with_flags):
        """Test get_bool method"""
        sdk = sdk_with_flags

        # Existing flag
        assert sdk.get_bool("user123", "bool_flag") is True
        
        # Non-existent flag with default
        assert sdk.get_bool("user123", "nonexistent", True) is True
        assert sdk.get_bool("user123", "nonexistent", False) is False

        # Inactive flag should return default
        assert sdk.get_bool("user123", "inactive_flag", False) is False

    def test_get_string(self, sdk_with_flags):
        """Test get_string method"""
        sdk = sdk_with_flags

        assert sdk.get_string("user123", "string_flag") == "test_value"
        assert sdk.get_string("user123", "nonexistent", "default") == "default"
        assert sdk.get_string("user123", "int_flag") == "42"  # Type conversion

    def test_get_int(self, sdk_with_flags):
        """Test get_int method"""
        sdk = sdk_with_flags

        assert sdk.get_int("user123", "int_flag") == 42
        assert sdk.get_int("user123", "nonexistent", 100) == 100

    def test_is_flag_enabled_for_user(self, sdk_with_flags):
        """Test is_flag_enabled_for_user method"""
        sdk = sdk_with_flags

        assert sdk.is_flag_enabled_for_user("user123", "bool_flag") is True
        assert sdk.is_flag_enabled_for_user("user123", "nonexistent") is False
        assert sdk.is_flag_enabled_for_user("user123", "inactive_flag") is False

    def test_get_user_flags(self, sdk_with_flags):
        """Test get_user_flags method"""
        sdk = sdk_with_flags

        # Get all flags
        all_flags = sdk.get_user_flags("user123")
        assert len(all_flags) == 4  # All flags including inactive
        assert all_flags["bool_flag"] is True
        assert all_flags["string_flag"] == "test_value"
        assert all_flags["inactive_flag"] is False  # Default for inactive

        # Get specific flags
        specific_flags = sdk.get_user_flags("user123", flag_keys=["bool_flag", "int_flag"])
        assert len(specific_flags) == 2
        assert "bool_flag" in specific_flags
        assert "int_flag" in specific_flags
        assert "string_flag" not in specific_flags

        # Invalid user ID should raise error
        with pytest.raises(FeatureFlagsHQError):
            sdk.get_user_flags("")


class TestInputValidation:
    """Test input validation and sanitization"""

    @pytest.fixture
    def sdk(self):
        """Create SDK instance for testing"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        yield sdk
        sdk.shutdown()

    def test_user_id_validation(self, sdk):
        """Test user ID validation"""
        # Valid user IDs should work
        sdk._validate_user_id("valid_user_123")
        sdk._validate_user_id("user@example.com")
        sdk._validate_user_id("user-name_123")

        # Invalid user IDs should raise errors
        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_user_id("")

        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_user_id(None)

        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_user_id("   ")  # Whitespace only

        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_user_id("user\nwith\nnewlines")

    def test_flag_key_validation(self, sdk):
        """Test flag key validation"""
        # Valid flag keys should work
        sdk._validate_flag_key("valid_flag")
        sdk._validate_flag_key("flag-name")
        sdk._validate_flag_key("flag123")

        # Invalid flag keys should raise errors
        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_flag_key("")

        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_flag_key(None)

        with pytest.raises(FeatureFlagsHQError):
            sdk._validate_flag_key("flag/with/slash")


class TestUtilityMethods:
    """Test utility and management methods"""

    @pytest.fixture
    def sdk(self):
        """Create SDK instance for testing"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        yield sdk
        sdk.shutdown()

    def test_get_all_flags(self, sdk):
        """Test get_all_flags method"""
        # Add test flag
        test_flag = FeatureFlagsHQFlag(
            name="test_flag", type="bool", value="true", is_active=True,
            created_at="2023-01-01T00:00:00Z", segments=None,
            rollout=FeatureFlagsHQRollout(percentage=75),
            version=2
        )
        sdk.feature_flags["test_flag"] = test_flag

        all_flags = sdk.get_all_flags()
        
        assert len(all_flags) == 1
        assert "test_flag" in all_flags
        flag_info = all_flags["test_flag"]
        assert flag_info["name"] == "test_flag"
        assert flag_info["type"] == "bool"
        assert flag_info["is_active"] is True
        assert flag_info["rollout_percentage"] == 75
        assert flag_info["version"] == 2

    def test_health_check(self, sdk):
        """Test health check method"""
        health = sdk.get_health_check()
        
        assert "status" in health
        assert "sdk_version" in health
        assert "cached_flags_count" in health
        assert "offline_mode" in health
        assert health["offline_mode"] is True
        assert health["sdk_version"] == __version__

    def test_get_stats(self, sdk):
        """Test get_stats method"""
        stats = sdk.get_stats()
        
        assert "total_user_accesses" in stats
        assert "unique_users_count" in stats
        assert "session_id" in stats
        assert "evaluation_times" in stats


class TestContextManager:
    """Test context manager functionality"""

    def test_context_manager_usage(self):
        """Test SDK as context manager"""
        with FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        ) as sdk:
            assert sdk is not None
            assert isinstance(sdk, FeatureFlagsHQSDK)


class TestFactoryFunction:
    """Test the factory function for creating clients"""

    def test_create_client_function(self):
        """Test create_client factory function"""
        client = create_client(
            client_id="test_client",
            client_secret="test_secret",
            environment="staging",
            offline_mode=True
        )

        try:
            assert isinstance(client, FeatureFlagsHQSDK)
            assert client.client_id == "test_client"
            assert client.client_secret == "test_secret"
            assert client.environment == "staging"
        finally:
            client.shutdown()

    def test_create_client_with_defaults(self):
        """Test create_client with default values"""
        client = create_client(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

        try:
            assert client.environment == "production"  # Default
            assert client.enable_metrics is True  # Default
        finally:
            client.shutdown()