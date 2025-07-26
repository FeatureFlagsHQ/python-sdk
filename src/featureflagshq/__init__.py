"""
FeatureFlagsHQ Python SDK

Official Python SDK for FeatureFlagsHQ - Enterprise feature flag management.
Visit: https://featureflagshq.com
"""

from .exceptions import (
    FeatureFlagsHQError,
    FeatureFlagsHQAuthError,
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQConfigError,
    FeatureFlagsHQTimeoutError
)
from .models import (
    FeatureFlagsHQFlag,
    FeatureFlagsHQSegment,
    FeatureFlagsHQRollout,
    FeatureFlagsHQUserAccessLog,
    FeatureFlagsHQSystemMetadata,
    __version__,
    BRAND_NAME
)
from .sdk import FeatureFlagsHQSDK, create_production_client

# Convenience aliases
FeatureFlagsHQ = FeatureFlagsHQSDK
FFHQ = FeatureFlagsHQSDK


def create_client(
        client_id: str,
        client_secret: str,
        environment: str = "production",
        **kwargs
) -> FeatureFlagsHQSDK:
    """
    Factory function to create a FeatureFlagsHQ client with sensible defaults

    Args:
        client_id: Your FeatureFlagsHQ client ID
        client_secret: Your FeatureFlagsHQ client secret
        environment: Environment name (production, staging, development)
        **kwargs: Additional configuration options

    Returns:
        Configured FeatureFlagsHQSDK instance

    Example:
        >>> import featureflagshq
        >>> client = featureflagshq.create_client("your-id", "your-secret")
        >>> enabled = client.is_flag_enabled_for_user("user123", "new_feature")
    """
    return create_production_client(
        client_id=client_id,
        client_secret=client_secret,
        environment=environment,
        **kwargs
    )


# Package metadata
__all__ = [
    # Main SDK class
    'FeatureFlagsHQSDK',
    'FeatureFlagsHQ',
    'FFHQ',

    # Factory function
    'create_client',

    # Exceptions
    'FeatureFlagsHQError',
    'FeatureFlagsHQAuthError',
    'FeatureFlagsHQNetworkError',
    'FeatureFlagsHQConfigError',
    'FeatureFlagsHQTimeoutError',

    # Models
    'FeatureFlagsHQFlag',
    'FeatureFlagsHQSegment',
    'FeatureFlagsHQRollout',
    'FeatureFlagsHQUserAccessLog',
    'FeatureFlagsHQSystemMetadata',

    # Metadata
    '__version__',
    'BRAND_NAME'
]

# Quick usage example in docstring
__doc__ += """

Quick Start:
    
    import featureflagshq
    
    # Create client
    client = featureflagshq.create_client(
        client_id="your-client-id",
        client_secret="your-client-secret"
    )
    
    # Check if feature is enabled for user
    if client.is_flag_enabled_for_user("user123", "new_dashboard"):
        # Show new dashboard
        pass
    
    # Get different types of flags
    max_items = client.get_int("user123", "max_items", default_value=10)
    welcome_msg = client.get_string("user123", "welcome_message", default_value="Hello!")
    
    # Use with segments for targeting
    segments = {"subscription": "premium", "region": "us-west"}
    premium_feature = client.get_bool("user123", "premium_feature", segments=segments)
    
    # Context manager for automatic cleanup
    with featureflagshq.create_client("client-id", "client-secret") as client:
        enabled = client.is_flag_enabled_for_user("user123", "feature")
"""
