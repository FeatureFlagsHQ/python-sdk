"""
Pytest configuration and fixtures for FeatureFlagsHQ SDK tests
"""

import os
import sys
import json
import pytest
import responses
from unittest.mock import Mock, patch

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Now import the SDK
try:
    import featureflagshq
    from featureflagshq.models import FeatureFlagsHQFlag, FeatureFlagsHQSegment, FeatureFlagsHQRollout
except ImportError as e:
    print(f"Failed to import featureflagshq: {e}")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Looking for package in: {src_path}")
    raise


@pytest.fixture
def mock_client_credentials():
    """Mock client credentials for testing"""
    return {
        'client_id': 'test-client-id',
        'client_secret': 'test-client-secret'
    }


@pytest.fixture
def sample_flag_data():
    """Sample flag data for testing"""
    return {
        'name': 'test_flag',
        'type': 'bool',
        'value': 'true',
        'is_active': True,
        'created_at': '2025-01-26T10:00:00Z',
        'segments': [
            {
                'name': 'premium_users',
                'type': 'string',
                'comparator': '==',
                'value': 'premium',
                'is_active': True,
                'created_at': '2025-01-26T10:00:00Z'
            }
        ],
        'rollout': {
            'percentage': 50,
            'sticky': True
        }
    }


@pytest.fixture
def sample_flag(sample_flag_data):
    """Create a sample FeatureFlagsHQFlag instance"""
    return FeatureFlagsHQFlag.from_dict(sample_flag_data)


@pytest.fixture
def mock_api_response():
    """Mock API response for testing"""
    return {
        'data': [
            {
                'name': 'feature_a',
                'type': 'bool',
                'value': 'true',
                'is_active': True,
                'created_at': '2025-01-26T10:00:00Z',
                'segments': [],
                'rollout': {'percentage': 100, 'sticky': True}
            },
            {
                'name': 'feature_b',
                'type': 'string',
                'value': 'hello',
                'is_active': True,
                'created_at': '2025-01-26T10:00:00Z',
                'segments': [],
                'rollout': {'percentage': 100, 'sticky': True}
            }
        ],
        'environment': {
            'name': 'test',
            'last_updated': '2025-01-26T10:00:00Z'
        }
    }


@pytest.fixture
def offline_client(mock_client_credentials):
    """Create an offline client for testing"""
    return featureflagshq.create_client(
        client_id=mock_client_credentials['client_id'],
        client_secret=mock_client_credentials['client_secret'],
        offline_mode=True,
        enable_metrics=False
    )


@pytest.fixture
def mock_responses():
    """Setup mock responses for HTTP requests"""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def online_client_with_mocks(mock_client_credentials, mock_api_response, mock_responses):
    """Create an online client with mocked API responses"""
    # Mock the flags endpoint
    mock_responses.add(
        responses.GET,
        'https://api.featureflagshq.com/v1/flags/',
        json=mock_api_response,
        status=200
    )
    
    # Mock the logs endpoint
    mock_responses.add(
        responses.POST,
        'https://api.featureflagshq.com/v1/logs/batch/',
        json={'status': 'success'},
        status=200
    )
    
    client = featureflagshq.create_client(
        client_id=mock_client_credentials['client_id'],
        client_secret=mock_client_credentials['client_secret'],
        polling_interval=60,  # Shorter for testing
        log_upload_interval=30,  # Shorter for testing
        enable_metrics=True
    )
    
    yield client
    
    # Cleanup
    client.shutdown()


@pytest.fixture
def user_segments():
    """Sample user segments for testing"""
    return {
        'subscription': 'premium',
        'region': 'us-west',
        'device': 'mobile',
        'age': 25,
        'is_beta_user': True
    }


@pytest.fixture
def mock_psutil():
    """Mock psutil for testing without dependency"""
    with patch('featureflagshq.models.psutil') as mock_psutil:
        mock_psutil.cpu_count.return_value = 4
        mock_memory = Mock()
        mock_memory.total = 8589934592  # 8GB
        mock_psutil.virtual_memory.return_value = mock_memory
        mock_process = Mock()
        mock_process.memory_info.return_value.rss = 104857600  # 100MB
        mock_psutil.Process.return_value = mock_process
        yield mock_psutil


# Test markers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Custom assertions
class CustomAssertions:
    """Custom assertion helpers for testing"""
    
    @staticmethod
    def assert_valid_flag_evaluation(result, expected_type=None):
        """Assert that a flag evaluation result is valid"""
        assert result is not None
        if expected_type:
            assert isinstance(result, expected_type)
    
    @staticmethod
    def assert_valid_segments(segments):
        """Assert that segments dictionary is valid"""
        assert isinstance(segments, dict)
        for key, value in segments.items():
            assert isinstance(key, str)
            assert key.strip() != ""
            assert len(key) <= 128


@pytest.fixture
def custom_assertions():
    """Provide custom assertion helpers"""
    return CustomAssertions