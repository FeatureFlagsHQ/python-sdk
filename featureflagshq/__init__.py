"""
FeatureFlagsHQ Python SDK

A secure, high-performance Python SDK for FeatureFlagsHQ feature flag management.
"""

from .sdk import FeatureFlagsHQSDK, create_production_client, validate_production_config

# SDK Constants
__version__ = "1.0.1"
SDK_VERSION = __version__
DEFAULT_API_BASE_URL = "https://api.featureflagshq.com"
COMPANY_NAME = "FeatureFlagsHQ"
USER_AGENT_PREFIX = f"{COMPANY_NAME}-Python-SDK"
__author__ = COMPANY_NAME
__email__ = "hello@featureflagshq.com"
__all__ = [
    "FeatureFlagsHQSDK", 
    "create_production_client", 
    "validate_production_config",
    "SDK_VERSION",
    "DEFAULT_API_BASE_URL", 
    "COMPANY_NAME",
    "USER_AGENT_PREFIX"
]