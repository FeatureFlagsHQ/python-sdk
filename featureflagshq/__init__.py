"""
FeatureFlagsHQ Python SDK

A secure, high-performance Python SDK for FeatureFlagsHQ feature flag management.
"""

from .sdk import FeatureFlagsHQSDK, create_production_client, validate_production_config

__version__ = "1.0.0"
__author__ = "FeatureFlagsHQ"
__email__ = "hello@featureflagshq.com"
__all__ = ["FeatureFlagsHQSDK", "create_production_client", "validate_production_config"]