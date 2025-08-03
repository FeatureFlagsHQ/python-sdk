"""
Unit tests for API response handling and validation

Tests various API response scenarios, malformed responses, and error conditions.
"""

import json
import pytest
import responses
from unittest.mock import Mock, patch
from requests.exceptions import HTTPError

from featureflagshq import FeatureFlagsHQSDK
from featureflagshq.exceptions import (
    FeatureFlagsHQAuthError,
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQConfigError
)


class TestAPIResponseHandling:
    """Test API response handling scenarios"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            timeout=1,
            offline_mode=True  # Start offline to control API calls
        )

    @pytest.mark.timeout(3)
    @responses.activate
    def test_successful_flags_response(self, sdk):
        """Test successful flags API response"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={
                "data": [
                    {
                        "name": "test_flag",
                        "type": "bool",
                        "value": "true",
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00Z",
                        "segments": [],
                        "rollout": {"percentage": 100, "sticky": True}
                    }
                ],
                "environment": {"name": "production"}
            },
            status=200
        )
        
        # Enable network mode temporarily
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        assert len(flags) == 1
        assert "test_flag" in flags
        assert flags["test_flag"].name == "test_flag"
        assert sdk.environment_info["name"] == "production"

    @pytest.mark.timeout(3)
    @responses.activate
    def test_malformed_json_response(self, sdk):
        """Test handling of malformed JSON response"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            body="invalid json{",
            status=200
        )
        
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        # Should return empty dict on malformed JSON
        assert flags == {}

    @pytest.mark.timeout(3)
    @responses.activate
    def test_missing_data_field_response(self, sdk):
        """Test response without data field"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={"environment": {"name": "test"}},  # Missing 'data' field
            status=200
        )
        
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        # Should handle gracefully and return empty dict
        assert flags == {}
        assert sdk.environment_info["name"] == "test"

    @pytest.mark.timeout(3)
    @responses.activate
    def test_invalid_flag_data_in_response(self, sdk):
        """Test response with invalid flag data"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={
                "data": [
                    {
                        "name": "valid_flag",
                        "type": "bool",
                        "value": "true",
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00Z",
                        "segments": [],
                        "rollout": {"percentage": 100, "sticky": True}
                    },
                    {
                        # Invalid flag missing required fields
                        "name": "invalid_flag",
                        "type": "bool"
                        # Missing 'value'
                    },
                    {
                        "name": "another_valid_flag",
                        "type": "string",
                        "value": "test",
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00Z",
                        "segments": [],
                        "rollout": {"percentage": 50, "sticky": True}
                    }
                ]
            },
            status=200
        )
        
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        # Should skip invalid flag but keep valid ones
        assert len(flags) == 2
        assert "valid_flag" in flags
        assert "another_valid_flag" in flags
        assert "invalid_flag" not in flags

    @pytest.mark.timeout(3)
    @responses.activate
    def test_empty_response(self, sdk):
        """Test empty API response"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={"data": []},
            status=200
        )
        
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        assert flags == {}

    @pytest.mark.timeout(3)
    @responses.activate
    def test_401_unauthorized_response(self, sdk):
        """Test 401 unauthorized response"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={"error": "Unauthorized"},
            status=401
        )
        
        sdk.offline_mode = False
        
        with pytest.raises(FeatureFlagsHQAuthError):
            sdk._fetch_flags()

    @pytest.mark.timeout(3)
    @responses.activate  
    def test_500_server_error_response(self, sdk):
        """Test 500 server error response"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={"error": "Internal server error"},
            status=500
        )
        
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        # Should return empty dict and record error
        assert flags == {}
        assert sdk.stats['errors']['network_errors'] > 0

    @pytest.mark.timeout(3)
    @responses.activate
    def test_partial_flag_data(self, sdk):
        """Test flag data with optional fields missing"""
        responses.add(
            responses.GET,
            'https://api.featureflagshq.com/v1/flags/',
            json={
                "data": [
                    {
                        "name": "minimal_flag",
                        "type": "bool",
                        "value": "true"
                        # Missing optional fields like is_active, created_at, etc.
                    }
                ]
            },
            status=200
        )
        
        sdk.offline_mode = False
        flags = sdk._fetch_flags()
        
        assert len(flags) == 1
        flag = flags["minimal_flag"]
        assert flag.name == "minimal_flag"
        assert flag.is_active is True  # Default value
        assert flag.rollout.percentage == 100  # Default rollout


class TestLogUploadResponses:
    """Test log upload API response handling"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=True
        )

    @pytest.mark.timeout(3)
    @responses.activate
    def test_successful_log_upload(self, sdk):
        """Test successful log upload"""
        responses.add(
            responses.POST,
            'https://api.featureflagshq.com/v1/logs/batch/',
            json={"status": "success", "processed": 5},
            status=200
        )
        
        # Add some logs to upload
        from featureflagshq.models import FeatureFlagsHQUserAccessLog
        from datetime import datetime, timezone
        
        for i in range(3):
            log = FeatureFlagsHQUserAccessLog(
                user_id=f"user{i}",
                flag_key="test_flag",
                flag_value=True,
                flag_type="bool",
                segments=None,
                evaluation_context={},
                evaluation_time_ms=1.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                session_id=sdk.session_id,
                request_id=f"req{i}"
            )
            sdk.user_access_logs.put(log)
        
        sdk.offline_mode = False
        sdk._upload_user_logs()
        
        # Should successfully upload
        assert sdk.user_access_logs.empty()

    @pytest.mark.timeout(3)
    @responses.activate
    def test_log_upload_failure_retry(self, sdk):
        """Test log upload failure and retry behavior"""
        responses.add(
            responses.POST,
            'https://api.featureflagshq.com/v1/logs/batch/',
            json={"error": "Server error"},
            status=500
        )
        
        # Add a log
        from featureflagshq.models import FeatureFlagsHQUserAccessLog
        from datetime import datetime, timezone
        
        log = FeatureFlagsHQUserAccessLog(
            user_id="user123",
            flag_key="test_flag",
            flag_value=True,
            flag_type="bool",
            segments=None,
            evaluation_context={},
            evaluation_time_ms=1.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=sdk.session_id,
            request_id="req123"
        )
        sdk.user_access_logs.put(log)
        
        sdk.offline_mode = False
        sdk._upload_user_logs()
        
        # Log should be put back for retry on failure
        assert not sdk.user_access_logs.empty()

    @pytest.mark.timeout(2)
    def test_circuit_breaker_blocks_upload(self, sdk):
        """Test that circuit breaker blocks log upload"""
        # Open circuit breaker
        sdk._circuit_breaker['state'] = 'open'
        
        # Add a log
        from featureflagshq.models import FeatureFlagsHQUserAccessLog
        from datetime import datetime, timezone
        
        log = FeatureFlagsHQUserAccessLog(
            user_id="user123",
            flag_key="test_flag",
            flag_value=True,
            flag_type="bool",
            segments=None,
            evaluation_context={},
            evaluation_time_ms=1.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=sdk.session_id,
            request_id="req123"
        )
        sdk.user_access_logs.put(log)
        
        # Should not attempt upload when circuit breaker is open
        sdk._upload_user_logs()
        
        # Log should remain in queue
        assert not sdk.user_access_logs.empty()


class TestHeaderGeneration:
    """Test request header generation and validation"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(2)
    def test_headers_generation(self, sdk):
        """Test proper header generation"""
        headers = sdk._get_headers('{"test": "payload"}')
        
        required_headers = [
            'Content-Type', 'X-SDK-Provider', 'X-Client-ID',
            'X-Timestamp', 'X-Signature', 'X-Session-ID',
            'X-SDK-Version', 'X-Environment', 'User-Agent'
        ]
        
        for header in required_headers:
            assert header in headers
        
        assert headers['Content-Type'] == 'application/json'
        assert headers['X-Client-ID'] == 'test_client'
        assert 'FeatureFlagsHQ' in headers['X-SDK-Provider']

    @pytest.mark.timeout(2)
    def test_custom_headers_merge(self, sdk):
        """Test custom headers are properly merged"""
        sdk.custom_headers = {'X-Custom': 'custom_value'}
        
        headers = sdk._get_headers('')
        
        assert 'X-Custom' in headers
        assert headers['X-Custom'] == 'custom_value'

    @pytest.mark.timeout(2)
    def test_sensitive_headers_not_logged(self, sdk):
        """Test that sensitive headers are not logged"""
        with patch('featureflagshq.sdk.logger') as mock_logger:
            mock_logger.isEnabledFor.return_value = True
            
            headers = sdk._get_headers('')
            
            # Check that debug logging doesn't include sensitive headers
            if mock_logger.debug.called:
                logged_args = str(mock_logger.debug.call_args)
                assert 'X-Signature' not in logged_args
                assert 'test_secret' not in logged_args