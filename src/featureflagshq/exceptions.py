"""
FeatureFlagsHQ SDK Exceptions

All custom exceptions for the FeatureFlagsHQ Python SDK.
"""
import time


class FeatureFlagsHQError(Exception):
    """Base exception for FeatureFlagsHQ SDK"""
    pass


class FeatureFlagsHQAuthError(FeatureFlagsHQError):
    """Authentication related errors"""
    pass


class FeatureFlagsHQNetworkError(FeatureFlagsHQError):
    """Network related errors"""
    pass


class FeatureFlagsHQConfigError(FeatureFlagsHQError):
    """Configuration related errors"""
    pass


class FeatureFlagsHQTimeoutError(FeatureFlagsHQError):
    """Request timeout errors"""
    pass


class SecureFeatureFlagsHQError(FeatureFlagsHQError):
    """Enhanced error class with security context"""

    def __init__(self, message: str, error_code: str = None,
                 context: dict = None, security_impact: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}
        self.security_impact = security_impact
        self.timestamp = time.time()
