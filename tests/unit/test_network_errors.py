"""
Unit tests for network error handling and circuit breaker functionality

Tests network errors, timeouts, retries, and circuit breaker patterns.
"""

import time
import pytest
import requests
from unittest.mock import Mock, patch
from requests.exceptions import ConnectionError, Timeout, HTTPError

from featureflagshq import FeatureFlagsHQSDK
from featureflagshq.exceptions import (
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQTimeoutError,
    FeatureFlagsHQAuthError
)


class TestNetworkErrorHandling:
    """Test network error handling scenarios"""

    @pytest.fixture
    def sdk(self):
        """Create SDK with shorter timeouts for testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            timeout=1,  # Short timeout for testing
            offline_mode=True  # Start offline to control network calls
        )

    @pytest.mark.timeout(2)
    def test_connection_error_handling(self, sdk):
        """Test handling of connection errors"""
        with patch.object(sdk.session, 'get', side_effect=ConnectionError("Connection failed")):
            flags = sdk._fetch_flags()
            
            # Should return empty dict on network error
            assert flags == {}
            
            # Should record the error in stats
            assert sdk.stats['errors']['network_errors'] > 0

    @pytest.mark.timeout(2)
    def test_timeout_error_handling(self, sdk):
        """Test handling of timeout errors"""
        with patch.object(sdk.session, 'get', side_effect=Timeout("Request timeout")):
            with pytest.raises(FeatureFlagsHQTimeoutError):
                sdk._fetch_flags()

    @pytest.mark.timeout(2)
    def test_http_error_handling(self, sdk):
        """Test handling of various HTTP errors"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = HTTPError("Server error")
        
        with patch.object(sdk.session, 'get', return_value=mock_response):
            flags = sdk._fetch_flags()
            assert flags == {}

    @pytest.mark.timeout(2)
    def test_auth_error_handling(self, sdk):
        """Test handling of authentication errors"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = HTTPError("Unauthorized")
        
        with patch.object(sdk.session, 'get', return_value=mock_response):
            with pytest.raises(FeatureFlagsHQAuthError):
                sdk._fetch_flags()


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for circuit breaker testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(3)
    def test_circuit_breaker_opens_after_failures(self, sdk):
        """Test that circuit breaker opens after repeated failures"""
        # Trigger multiple failures
        for _ in range(6):  # More than failure threshold (5)
            sdk._record_api_failure()
        
        # Circuit breaker should be open
        assert sdk._circuit_breaker['state'] == 'open'
        assert not sdk._check_circuit_breaker()

    @pytest.mark.timeout(3)
    def test_circuit_breaker_recovery(self, sdk):
        """Test circuit breaker recovery after timeout"""
        # Open the circuit breaker
        sdk._circuit_breaker['state'] = 'open'
        sdk._circuit_breaker['last_failure_time'] = time.time() - 70  # Past recovery timeout
        
        # Should move to half-open
        assert sdk._check_circuit_breaker()
        assert sdk._circuit_breaker['state'] == 'half-open'

    @pytest.mark.timeout(2)
    def test_circuit_breaker_closes_on_success(self, sdk):
        """Test circuit breaker closes after successful call"""
        sdk._circuit_breaker['state'] = 'half-open'
        
        sdk._record_api_success()
        
        assert sdk._circuit_breaker['state'] == 'closed'
        assert sdk._circuit_breaker['failure_count'] == 0


class TestRateLimitingAndSecurity:
    """Test rate limiting and security features"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for rate limiting tests"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(2)
    def test_rate_limit_cleanup(self, sdk):
        """Test that old rate limit entries are cleaned up"""
        # Add old entries
        old_time = time.time() - 120  # 2 minutes ago
        sdk._rate_limits['old_user'] = (10, old_time)
        sdk._rate_limits['current_user'] = (5, time.time())
        
        # Check rate limit (should clean up old entries)
        sdk._rate_limit_check('new_user')
        
        # Old entry should be removed
        assert 'old_user' not in sdk._rate_limits
        assert 'current_user' in sdk._rate_limits

    @pytest.mark.timeout(2)
    def test_security_stats_tracking(self, sdk):
        """Test security statistics tracking"""
        initial_blocked = sdk._security_stats['blocked_malicious_requests']
        
        # Trigger security violation
        try:
            sdk._validate_user_id("user\x00with\x00nulls")
        except:
            pass
        
        # Should increment security stats
        assert sdk._security_stats['blocked_malicious_requests'] > initial_blocked

    @pytest.mark.timeout(2)
    def test_memory_monitoring(self, sdk):
        """Test memory monitoring functionality"""
        # Mock psutil for testing
        with patch('featureflagshq.sdk.psutil') as mock_psutil:
            mock_process = Mock()
            mock_process.memory_info.return_value.rss = 600 * 1024 * 1024  # 600MB (over threshold)
            mock_psutil.Process.return_value = mock_process
            
            # Should trigger memory check without error
            sdk._memory_monitor.check_memory_usage(sdk)
            
            # Should handle gracefully if psutil fails
            mock_psutil.Process.side_effect = Exception("psutil error")
            sdk._memory_monitor.check_memory_usage(sdk)  # Should not raise


class TestBackgroundTasks:
    """Test background task functionality"""

    @pytest.fixture
    def sdk(self):
        """Create SDK for background task testing"""
        return FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )

    @pytest.mark.timeout(3)
    def test_stats_cleanup(self, sdk):
        """Test periodic statistics cleanup"""
        # Add many users to trigger cleanup
        for i in range(12000):  # More than MAX_UNIQUE_USERS_TRACKED
            sdk.stats['unique_users'].add(f'user{i}')
        
        sdk._cleanup_old_stats()
        
        # Should be limited to max tracked users
        assert len(sdk.stats['unique_users']) <= sdk.MAX_UNIQUE_USERS_TRACKED

    @pytest.mark.timeout(2)
    def test_timing_stats_update(self, sdk):
        """Test timing statistics updates"""
        # Test timing stats update
        sdk._update_timing_stats(15.5)
        sdk._update_timing_stats(25.2)
        
        timing_stats = sdk.stats['evaluation_times']
        assert timing_stats['count'] == 2
        assert timing_stats['total_ms'] == 40.7
        assert timing_stats['min_ms'] == 15.5
        assert timing_stats['max_ms'] == 25.2
        assert timing_stats['avg_ms'] == 20.35

    @pytest.mark.timeout(2)
    def test_shutdown_with_background_tasks(self, sdk):
        """Test shutdown behavior with background tasks"""
        # Mock active threads
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread.join = Mock()
        
        sdk._polling_thread = mock_thread
        sdk._log_upload_thread = mock_thread
        
        # Shutdown should complete within timeout
        sdk.shutdown()
        
        # Threads should be joined
        assert mock_thread.join.call_count >= 2