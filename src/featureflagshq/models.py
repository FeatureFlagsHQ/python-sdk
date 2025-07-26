"""
FeatureFlagsHQ SDK Models

Data models for the FeatureFlagsHQ Python SDK.
"""

import base64
import contextlib
import hashlib
import hmac
import json
import logging
import os
import platform
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

__version__ = "1.0.0"
BRAND_NAME = 'FeatureFlagsHQ'

try:
    import psutil
except ImportError:
    psutil = None

# Setup logging
logger = logging.getLogger(f'{BRAND_NAME.lower()}_sdk')


@contextlib.contextmanager
def measure_time():
    """Context manager to measure execution time in milliseconds"""
    start_time = time.perf_counter()
    try:
        yield lambda: (time.perf_counter() - start_time) * 1000
    finally:
        pass


def generate_featureflagshq_signature(client_id: str, client_secret: str, payload: str, timestamp: str = None) -> tuple[
    str, str]:
    """Generate HMAC signature for FeatureFlagsHQ API authentication"""
    if timestamp is None:
        timestamp = str(int(time.time()))

    message = f"{client_id}:{timestamp}:{payload}"
    signature = hmac.new(
        client_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    return signature_b64, timestamp


def validate_hmac_signature(client_id: str, client_secret: str,
                            payload: str, timestamp: str,
                            received_signature: str) -> bool:
    """Validate HMAC signature to prevent tampering"""
    try:
        expected_signature, _ = generate_featureflagshq_signature(
            client_id, client_secret, payload, timestamp
        )

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, received_signature)
    except Exception:
        return False


@dataclass
class FeatureFlagsHQSegment:
    """Represents a FeatureFlagsHQ segment for user matching"""
    name: str
    type: str
    comparator: str
    value: str
    is_active: bool
    created_at: str

    def matches_segment(self, segment_value: Any) -> bool:
        """Check if segment value matches this FeatureFlagsHQ segment"""
        if not self.is_active:
            return False

        try:
            # Type coercion with validation
            if self.type == "float":
                segment_val = float(self.value)
                user_val = float(segment_value)
            elif self.type == "int":
                segment_val = int(self.value)
                user_val = int(segment_value)
            elif self.type == "bool":
                segment_val = str(self.value).lower() == "true"
                user_val = bool(segment_value)
            else:  # string
                segment_val = str(self.value)
                user_val = str(segment_value)

            # Apply comparator
            if self.comparator == "==":
                return user_val == segment_val
            elif self.comparator == "!=":
                return user_val != segment_val
            elif self.comparator == ">":
                return user_val > segment_val
            elif self.comparator == ">=":
                return user_val >= segment_val
            elif self.comparator == "<":
                return user_val < segment_val
            elif self.comparator == "<=":
                return user_val <= segment_val
            elif self.comparator == "contains":
                return segment_val in str(user_val)
            elif self.comparator == "starts_with":
                return str(user_val).startswith(segment_val)
            elif self.comparator == "ends_with":
                return str(user_val).endswith(segment_val)
            elif self.comparator == "regex":
                import re
                return bool(re.search(segment_val, str(user_val)))
            elif self.comparator == "in":
                values = [v.strip() for v in segment_val.split(',')]
                return str(user_val) in values
            else:
                logger.warning(f"Unknown FeatureFlagsHQ comparator: {self.comparator}")
                return False

        except (ValueError, TypeError, ImportError) as e:
            logger.warning(f"Error comparing FeatureFlagsHQ segment {self.name}: {e}")
            return False


@dataclass
class FeatureFlagsHQRollout:
    """Represents FeatureFlagsHQ rollout configuration"""
    percentage: int
    sticky: bool = True


@dataclass
class FeatureFlagsHQFlag:
    """Represents a FeatureFlagsHQ feature flag with segments and rollout"""
    name: str
    type: str
    value: str
    is_active: bool
    created_at: str
    segments: Optional[List[FeatureFlagsHQSegment]]
    rollout: FeatureFlagsHQRollout
    updated_at: Optional[str] = None
    version: int = 1

    @classmethod
    def from_dict(cls, data: Dict) -> 'FeatureFlagsHQFlag':
        """Create FeatureFlagsHQFlag from dictionary with validation"""
        try:
            segments = None
            if data.get('segments'):
                segments = [FeatureFlagsHQSegment(**segment) for segment in data['segments']]

            rollout_data = data.get('rollout', {'percentage': 100, 'sticky': True})
            rollout = FeatureFlagsHQRollout(**rollout_data)

            return cls(
                name=data['name'],
                type=data['type'],
                value=data['value'],
                is_active=data.get('is_active', True),
                created_at=data.get('created_at', datetime.now(timezone.utc).isoformat()),
                segments=segments,
                rollout=rollout,
                updated_at=data.get('updated_at'),
                version=data.get('version', 1)
            )
        except KeyError as e:
            from .exceptions import FeatureFlagsHQConfigError
            raise FeatureFlagsHQConfigError(f"Missing required field in flag data: {e}")

    def evaluate_for_user(
            self,
            user_id: str,
            segments: Optional[Dict[str, Any]] = None
    ) -> tuple[Any, Dict[str, Any]]:
        """Evaluate FeatureFlagsHQ flag for a specific user"""
        with measure_time() as get_evaluation_time:
            evaluation_context = {
                'flag_active': self.is_active,
                'segments_matched': [],
                'segments_evaluated': [],
                'rollout_qualified': False,
                'default_value_used': False,
                'provider': BRAND_NAME,
                'flag_version': self.version,
                'evaluation_reason': 'unknown'
            }

            if not self.is_active:
                evaluation_context['default_value_used'] = True
                evaluation_context['evaluation_reason'] = 'flag_inactive'
                result = self._get_typed_default_value(), evaluation_context
            else:
                # Check segments
                segments_pass = True
                if self.segments and segments:
                    segments_pass = False
                    for segment in self.segments:
                        evaluation_context['segments_evaluated'].append(segment.name)
                        if segment.name in segments:
                            if segment.matches_segment(segments[segment.name]):
                                evaluation_context['segments_matched'].append(segment.name)
                                segments_pass = True
                                break
                elif self.segments and not segments:
                    segments_pass = False
                    evaluation_context['evaluation_reason'] = 'segments_required_but_not_provided'

                if not segments_pass:
                    evaluation_context['default_value_used'] = True
                    evaluation_context['evaluation_reason'] = 'segments_not_matched'
                    result = self._get_typed_default_value(), evaluation_context
                else:
                    # Check rollout with sticky behavior
                    if self.rollout.percentage < 100:
                        user_hash = hashlib.sha256(f"{self.name}_{user_id}_{self.version}".encode()).hexdigest()
                        user_percentage = int(user_hash[:8], 16) % 100
                        if user_percentage >= self.rollout.percentage:
                            evaluation_context['default_value_used'] = True
                            evaluation_context['evaluation_reason'] = 'rollout_not_qualified'
                            result = self._get_typed_default_value(), evaluation_context
                        else:
                            evaluation_context['rollout_qualified'] = True
                            evaluation_context['evaluation_reason'] = 'rollout_qualified'
                            result = self._get_typed_value(), evaluation_context
                    else:
                        evaluation_context['rollout_qualified'] = True
                        evaluation_context['evaluation_reason'] = 'full_rollout'
                        result = self._get_typed_value(), evaluation_context

            evaluation_context['evaluation_time_ms'] = round(get_evaluation_time(), 3)
            return result

    def _get_typed_value(self) -> Any:
        """Convert string value to appropriate type with validation"""
        try:
            if self.type == "bool":
                return str(self.value).lower() in ("true", "1", "yes", "on")
            elif self.type == "int":
                return int(float(self.value))
            elif self.type == "float":
                return float(self.value)
            elif self.type == "json":
                return json.loads(self.value)
            else:
                return str(self.value)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Error converting flag value {self.value} to type {self.type}: {e}")
            return self._get_typed_default_value()

    def _get_typed_default_value(self) -> Any:
        """Get appropriate default value based on type"""
        if self.type == "bool":
            return False
        elif self.type == "int":
            return 0
        elif self.type == "float":
            return 0.0
        elif self.type == "json":
            return {}
        else:
            return ""


@dataclass
class FeatureFlagsHQUserAccessLog:
    """Represents a FeatureFlagsHQ user-specific feature flag access log entry"""
    user_id: str
    flag_key: str
    flag_value: Any
    flag_type: str
    segments: Optional[Dict[str, Any]]
    evaluation_context: Dict[str, Any]
    evaluation_time_ms: float
    timestamp: str
    session_id: str
    request_id: str
    sdk_provider: str = "FeatureFlagsHQ"
    sdk_version: str = __version__
    metadata: Optional[Dict] = None

    def __post_init__(self):
        """Generate request ID if not provided and ensure data integrity"""
        if not hasattr(self, 'request_id') or not self.request_id:
            self.request_id = str(uuid.uuid4())[:16]

        # Create a copy to avoid modifying original segments
        if self.segments:
            self.segments = {k: v for k, v in self.segments.items()}


@dataclass
class FeatureFlagsHQSystemMetadata:
    """FeatureFlagsHQ system metadata for analytics"""
    platform: str
    python_version: str
    cpu_count: int
    memory_total: int
    hostname: str
    process_id: int
    sdk_version: str = __version__

    @classmethod
    def collect(cls):
        return cls(
            platform=platform.platform(),
            python_version=platform.python_version(),
            cpu_count=psutil.cpu_count() if psutil else 1,
            memory_total=psutil.virtual_memory().total if psutil else 0,
            hostname=platform.node(),
            process_id=os.getpid()
        )
