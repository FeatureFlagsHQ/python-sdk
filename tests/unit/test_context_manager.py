"""
Unit tests for context manager functionality and edge cases

Tests context manager behavior, exception handling during shutdown, and cleanup.
"""

import pytest
import time
from unittest.mock import Mock, patch

from featureflagshq import FeatureFlagsHQSDK, create_client
from featureflagshq.exceptions import FeatureFlagsHQError


class TestContextManagerBasics:
    """Test basic context manager functionality"""

    @pytest.mark.timeout(3)
    def test_basic_context_manager(self):
        """Test basic context manager usage"""
        with FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        ) as sdk:
            assert sdk is not None
            assert isinstance(sdk, FeatureFlagsHQSDK)
            assert sdk.session_id is not None
            
            # Should be functional within context
            result = sdk.get_bool("user123", "nonexistent_flag", True)
            assert result is True

    @pytest.mark.timeout(3)
    def test_context_manager_with_factory(self):
        """Test context manager with factory function"""
        with create_client(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        ) as client:
            assert isinstance(client, FeatureFlagsHQSDK)
            
            # Should work normally
            result = client.is_flag_enabled_for_user("user123", "test_flag")
            assert result is False  # Default for non-existent flag

    @pytest.mark.timeout(3)
    def test_nested_context_managers(self):
        """Test nested context manager usage"""
        with create_client(
            client_id="outer_client",
            client_secret="outer_secret",
            offline_mode=True
        ) as outer_client:
            with create_client(
                client_id="inner_client", 
                client_secret="inner_secret",
                offline_mode=True
            ) as inner_client:
                # Both should work independently
                assert outer_client.client_id == "outer_client"
                assert inner_client.client_id == "inner_client"
                
                outer_result = outer_client.get_bool("user1", "flag1", True)
                inner_result = inner_client.get_bool("user2", "flag2", False)
                
                assert outer_result is True
                assert inner_result is False


class TestExceptionHandlingInContextManager:
    """Test exception handling within context manager"""

    @pytest.mark.timeout(3)
    def test_exception_during_context_manager_execution(self):
        """Test that exceptions during execution don't prevent cleanup"""
        try:
            with FeatureFlagsHQSDK(
                client_id="test_client",
                client_secret="test_secret",
                offline_mode=True
            ) as sdk:
                # Simulate an exception during execution
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected exception
        
        # SDK should have been properly cleaned up despite the exception

    @pytest.mark.timeout(3)
    def test_exception_during_shutdown(self):
        """Test handling of exceptions during shutdown"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        # Mock session.close to raise an exception
        with patch.object(sdk.session, 'close', side_effect=Exception("Close error")):
            # Should handle shutdown exception gracefully
            with sdk:
                pass  # Normal execution
        
        # Should complete without raising the shutdown exception

    @pytest.mark.timeout(3)
    def test_multiple_shutdown_calls(self):
        """Test that multiple shutdown calls are safe"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        with sdk:
            # Call shutdown manually
            sdk.shutdown()
        
        # Context manager exit should call shutdown again safely
        # This should not raise any exceptions

    @pytest.mark.timeout(3)
    def test_context_manager_with_background_threads(self):
        """Test context manager cleanup with background threads"""
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread_instance.is_alive.return_value = True
            mock_thread_instance.join = Mock()
            mock_thread.return_value = mock_thread_instance
            
            with FeatureFlagsHQSDK(
                client_id="test_client",
                client_secret="test_secret",
                polling_interval=60,  # Enable background threads
                offline_mode=False
            ) as sdk:
                # Threads should be created
                pass
            
            # Threads should be joined on exit
            assert mock_thread_instance.join.called


class TestDestructorBehavior:
    """Test destructor (__del__) behavior"""

    @pytest.mark.timeout(3)
    def test_destructor_calls_shutdown(self):
        """Test that destructor calls shutdown if not already called"""
        with patch.object(FeatureFlagsHQSDK, 'shutdown') as mock_shutdown:
            sdk = FeatureFlagsHQSDK(
                client_id="test_client",
                client_secret="test_secret",
                offline_mode=True
            )
            
            # Don't call shutdown manually
            sdk.__del__()
            
            # Destructor should call shutdown
            mock_shutdown.assert_called_once()

    @pytest.mark.timeout(2)
    def test_destructor_handles_exceptions(self):
        """Test that destructor handles exceptions gracefully"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        # Mock shutdown to raise an exception
        with patch.object(sdk, 'shutdown', side_effect=Exception("Shutdown error")):
            # Destructor should handle this gracefully
            sdk.__del__()  # Should not raise

    @pytest.mark.timeout(2)
    def test_destructor_with_already_shutdown(self):
        """Test destructor when SDK is already shutdown"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        # Shutdown manually first
        sdk.shutdown()
        
        # Destructor should handle this gracefully
        sdk.__del__()  # Should not raise or double-shutdown


class TestCleanupVerification:
    """Test that cleanup is properly performed"""

    @pytest.mark.timeout(3)
    def test_stop_event_is_set(self):
        """Test that stop event is properly set during shutdown"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        with sdk:
            assert not sdk._stop_event.is_set()
        
        # After context exit, stop event should be set
        assert sdk._stop_event.is_set()

    @pytest.mark.timeout(3)
    def test_session_cleanup(self):
        """Test that HTTP session is properly closed"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        session = sdk.session
        
        with patch.object(session, 'close') as mock_close:
            with sdk:
                pass
            
            # Session close should be called
            mock_close.assert_called_once()

    @pytest.mark.timeout(3)
    def test_final_log_upload_attempt(self):
        """Test that final log upload is attempted during shutdown"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=True
        )
        
        with patch.object(sdk, '_upload_user_logs') as mock_upload:
            with sdk:
                pass
            
            # Should attempt final upload
            mock_upload.assert_called()


class TestResourceManagement:
    """Test resource management and memory cleanup"""

    @pytest.mark.timeout(3)
    def test_thread_cleanup_timeout(self):
        """Test thread cleanup with timeout"""
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread.join = Mock()
        
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True
        )
        
        sdk._polling_thread = mock_thread
        sdk._log_upload_thread = mock_thread
        
        with sdk:
            pass
        
        # Threads should be joined with timeout
        assert mock_thread.join.call_count == 2
        # Verify timeout parameter was passed
        for call in mock_thread.join.call_args_list:
            assert 'timeout' in call.kwargs or len(call.args) > 0

    @pytest.mark.timeout(3)
    def test_queue_cleanup(self):
        """Test that queues are properly handled during cleanup"""
        sdk = FeatureFlagsHQSDK(
            client_id="test_client",
            client_secret="test_secret",
            offline_mode=True,
            enable_metrics=True
        )
        
        # Add items to queue
        from featureflagshq.models import FeatureFlagsHQUserAccessLog
        from datetime import datetime, timezone
        
        log = FeatureFlagsHQUserAccessLog(
            user_id="user123", flag_key="test_flag", flag_value=True,
            flag_type="bool", segments=None, evaluation_context={},
            evaluation_time_ms=1.0, timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=sdk.session_id, request_id="req123"
        )
        sdk.user_access_logs.put(log)
        
        with sdk:
            assert not sdk.user_access_logs.empty()
        
        # Queue should still exist but final upload should have been attempted