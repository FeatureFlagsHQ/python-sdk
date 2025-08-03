"""
FeatureFlagsHQ SDK Main Class

Core SDK implementation for FeatureFlagsHQ Python SDK.
"""

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import Any, Dict, Optional, List, Callable
from urllib.parse import urlparse

import psutil
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    FeatureFlagsHQError,
    FeatureFlagsHQAuthError,
    FeatureFlagsHQNetworkError,
    FeatureFlagsHQConfigError,
    FeatureFlagsHQTimeoutError
)
from .models import (
    FeatureFlagsHQFlag,
    FeatureFlagsHQUserAccessLog,
    FeatureFlagsHQSystemMetadata,
    generate_featureflagshq_signature,
    measure_time,
    BRAND_NAME,
    __version__
)


# Security utilities
def sanitize_log_data(data: Any) -> Any:
    """Sanitize data before logging to prevent log injection"""
    if isinstance(data, str):
        # Remove potential log injection characters
        return data.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    elif isinstance(data, dict):
        return {k: sanitize_log_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    else:
        return data


class SecurityFilter(logging.Filter):
    """Filter to prevent sensitive data from being logged"""

    SENSITIVE_PATTERNS = [
        re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE),
        re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE),
        re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE),
        re.compile(r'signature["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE),
    ]

    def filter(self, record):
        # Sanitize the log message
        if hasattr(record, 'msg'):
            message = str(record.msg)
            for pattern in self.SENSITIVE_PATTERNS:
                message = pattern.sub(r'\1[REDACTED]', message)
            record.msg = message

        return True


class MemoryMonitor:
    """Monitor memory usage and prevent memory leaks"""

    def __init__(self, threshold_mb: int = 500):
        self.threshold_bytes = threshold_mb * 1024 * 1024
        self.last_check = time.time()

    def check_memory_usage(self, sdk_instance):
        """Check if memory usage is within acceptable limits"""
        current_time = time.time()

        # Check every 5 minutes
        if current_time - self.last_check < 300:
            return

        try:
            if psutil:
                process = psutil.Process()
                memory_usage = process.memory_info().rss

                if memory_usage > self.threshold_bytes:
                    logger.warning(f"High memory usage detected: {memory_usage / 1024 / 1024:.1f} MB")

                    # Force cleanup
                    if hasattr(sdk_instance, '_cleanup_old_stats'):
                        sdk_instance._cleanup_old_stats()

                    # Force garbage collection
                    import gc
                    gc.collect()
        except Exception:
            pass  # Handle gracefully if psutil not available

        self.last_check = current_time


# Setup secure logging
class FeatureFlagsHQFormatter(logging.Formatter):
    def format(self, record):
        record.service = BRAND_NAME
        return super().format(record)


logger = logging.getLogger(f'{BRAND_NAME.lower()}_sdk')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(FeatureFlagsHQFormatter(
        '%(asctime)s - %(service)s - %(levelname)s - %(message)s'
    ))
    handler.addFilter(SecurityFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FeatureFlagsHQSDK:
    """
    Security-hardened FeatureFlagsHQ Python SDK
    Enterprise-grade feature flag management with comprehensive security controls
    """

    # Security constants
    MAX_USER_ID_LENGTH = 256
    MAX_FLAG_KEY_LENGTH = 128
    MAX_UNIQUE_USERS_TRACKED = 10000
    MAX_UNIQUE_FLAGS_TRACKED = 1000
    SENSITIVE_HEADERS = {'X-Signature', 'Authorization', 'X-Client-Secret'}
    ALLOWED_URL_SCHEMES = {'http', 'https'}

    def __init__(
            self,
            api_base_url: str = "https://api.featureflagshq.com",
            client_id: str = None,
            client_secret: str = None,
            polling_interval: int = 300,  # 5 minutes
            log_upload_interval: int = 120,  # 2 minutes
            max_logs_batch: int = 100,
            timeout: int = 30,
            max_retries: int = 3,
            backoff_factor: float = 0.3,
            enable_metrics: bool = True,
            environment: str = "production",
            offline_mode: bool = False,
            debug: bool = False,
            custom_headers: Optional[Dict[str, str]] = None,
            on_flag_change: Optional[Callable[[str, Any, Any], None]] = None
    ):
        # Security validation first
        if not client_id or not client_secret:
            raise FeatureFlagsHQConfigError("FeatureFlagsHQ client_id and client_secret are required")

        if not isinstance(polling_interval, int) or polling_interval < 30:
            raise FeatureFlagsHQConfigError("Polling interval must be at least 30 seconds")

        # Validate and sanitize inputs
        self.api_base_url = self._validate_and_sanitize_url(api_base_url)
        self.client_id = client_id
        self.client_secret = client_secret
        self.polling_interval = polling_interval
        self.log_upload_interval = log_upload_interval
        self.max_logs_batch = max_logs_batch
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.enable_metrics = enable_metrics
        self.environment = environment
        self.offline_mode = offline_mode
        self.debug = debug
        self.custom_headers = self._validate_custom_headers(custom_headers or {})
        self.on_flag_change = on_flag_change

        if debug:
            logger.setLevel(logging.DEBUG)

        # Initialize security monitoring
        self._security_stats = {
            'blocked_malicious_requests': 0,
            'invalid_input_attempts': 0,
            'suspicious_activity_detected': 0
        }

        # Initialize rate limiting
        self._rate_limits = {}

        # Enhanced HTTP session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # In-memory storage with thread locks
        self._flags_lock = threading.RLock()
        self._stats_lock = threading.Lock()
        self.feature_flags: Dict[str, FeatureFlagsHQFlag] = {}
        self.environment_info: Dict[str, Any] = {}
        self.user_access_logs: Queue = Queue()
        self.session_id = str(uuid.uuid4())
        self.system_metadata = FeatureFlagsHQSystemMetadata.collect()

        # Threading controls
        self._stop_event = threading.Event()
        self._polling_thread: Optional[threading.Thread] = None
        self._log_upload_thread: Optional[threading.Thread] = None

        # Enhanced statistics
        self.stats = {
            'total_user_accesses': 0,
            'unique_users': set(),
            'unique_flags_accessed': set(),
            'last_sync': None,
            'last_log_upload': None,
            'segment_matches': 0,
            'rollout_evaluations': 0,
            'sdk_provider': BRAND_NAME,
            'sdk_version': __version__,
            'evaluation_times': {
                'total_ms': 0.0,
                'count': 0,
                'min_ms': float('inf'),
                'max_ms': 0.0,
                'avg_ms': 0.0
            },
            'api_calls': {
                'successful': 0,
                'failed': 0,
                'total': 0
            },
            'errors': {
                'network_errors': 0,
                'auth_errors': 0,
                'config_errors': 0,
                'other_errors': 0
            }
        }

        # Circuit breaker for API calls
        self._circuit_breaker = {
            'failure_count': 0,
            'last_failure_time': None,
            'state': 'closed',  # closed, open, half-open
            'failure_threshold': 5,
            'recovery_timeout': 60  # seconds
        }

        # Memory monitoring
        self._memory_monitor = MemoryMonitor()

        # Initialize SDK
        if not offline_mode:
            self._initial_fetch()
            self._start_background_tasks()
        else:
            logger.info("FeatureFlagsHQ: SDK initialized in offline mode")

    def _validate_and_sanitize_url(self, url: str) -> str:
        """Validate and sanitize API base URL"""
        if not url or not isinstance(url, str):
            raise FeatureFlagsHQConfigError("API base URL must be a non-empty string")

        try:
            parsed = urlparse(url)

            # Validate scheme
            if parsed.scheme not in self.ALLOWED_URL_SCHEMES:
                raise FeatureFlagsHQConfigError(f"Invalid URL scheme. Only {self.ALLOWED_URL_SCHEMES} are allowed")

            # Validate hostname
            if not parsed.netloc:
                raise FeatureFlagsHQConfigError("Invalid URL: missing hostname")

            # Prevent localhost/internal network access in production
            if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
                logger.warning("Using localhost URL - ensure this is intended for development only")

            # Remove trailing slash for consistency
            return url.rstrip('/')

        except Exception as e:
            raise FeatureFlagsHQConfigError(f"Invalid API base URL: {e}")

    def _validate_custom_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Validate and sanitize custom headers"""
        if not isinstance(headers, dict):
            raise FeatureFlagsHQConfigError("Custom headers must be a dictionary")

        sanitized_headers = {}

        for key, value in headers.items():
            # Validate header key
            if not isinstance(key, str) or not key:
                logger.warning(f"Skipping invalid header key: {key}")
                continue

            # Check for dangerous characters in key
            if any(char in key for char in ['\n', '\r', '\0', ':']):
                logger.warning(f"Skipping header with dangerous characters: {key}")
                self._security_stats['blocked_malicious_requests'] += 1
                continue

            # Validate header value
            if not isinstance(value, str):
                value = str(value)

            # Sanitize header value
            value = value.replace('\n', '').replace('\r', '').replace('\0', '')

            # Limit header length
            if len(key) > 128 or len(value) > 1024:
                logger.warning(f"Skipping oversized header: {key}")
                continue

            sanitized_headers[key] = value

        return sanitized_headers

    def _validate_user_id(self, user_id: Any) -> str:
        """Enhanced user ID validation with security checks"""
        if user_id is None:
            raise FeatureFlagsHQError("user_id cannot be None")

        if not isinstance(user_id, str):
            raise FeatureFlagsHQError("user_id must be a string")

        if not user_id.strip():
            raise FeatureFlagsHQError("user_id cannot be empty or whitespace")

        user_id = user_id.strip()

        # Length validation
        if len(user_id) > self.MAX_USER_ID_LENGTH:
            raise FeatureFlagsHQError(f"user_id too long (max {self.MAX_USER_ID_LENGTH} characters)")

        # Character validation - prevent injection attacks
        dangerous_chars = ['\n', '\r', '\0', '\t', '\x1b']
        if any(char in user_id for char in dangerous_chars):
            self._security_stats['blocked_malicious_requests'] += 1
            raise FeatureFlagsHQError("user_id contains invalid characters")

        # Pattern validation - basic alphanumeric + common safe chars
        if not re.match(r'^[a-zA-Z0-9_@\.\-\+]+$', user_id):
            logger.warning(f"Potentially unsafe user_id pattern: {user_id[:50]}...")
            self._security_stats['suspicious_activity_detected'] += 1

        return user_id

    def _validate_flag_key(self, flag_key: Any) -> str:
        """Enhanced flag key validation with security checks"""
        if flag_key is None:
            raise FeatureFlagsHQError("flag_key cannot be None")

        if not isinstance(flag_key, str):
            raise FeatureFlagsHQError("flag_key must be a string")

        if not flag_key.strip():
            raise FeatureFlagsHQError("flag_key cannot be empty or whitespace")

        flag_key = flag_key.strip()

        # Length validation
        if len(flag_key) > self.MAX_FLAG_KEY_LENGTH:
            raise FeatureFlagsHQError(f"flag_key too long (max {self.MAX_FLAG_KEY_LENGTH} characters)")

        # Character validation
        dangerous_chars = ['\n', '\r', '\0', '\t', '\x1b', '/', '\\', '..']
        if any(char in flag_key for char in dangerous_chars):
            self._security_stats['blocked_malicious_requests'] += 1
            raise FeatureFlagsHQError("flag_key contains invalid characters")

        # Pattern validation - alphanumeric + underscores/hyphens
        if not re.match(r'^[a-zA-Z0-9_\-]+$', flag_key):
            self._security_stats['suspicious_activity_detected'] += 1
            raise FeatureFlagsHQError("flag_key contains invalid characters")

        return flag_key

    def _sanitize_segments(self, segments: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize user segments to prevent injection"""
        if not segments or not isinstance(segments, dict):
            return segments

        sanitized = {}
        for key, value in segments.items():
            # Sanitize key
            if not isinstance(key, str) or not key:
                continue

            key = key.strip()
            if len(key) > 128:  # Reasonable limit
                continue

            # Sanitize value based on type
            if isinstance(value, str):
                # Remove dangerous characters
                value = value.replace('\n', '').replace('\r', '').replace('\0', '')
                if len(value) > 1024:  # Reasonable limit
                    value = value[:1024]
            elif isinstance(value, (int, float, bool)):
                pass  # These types are safe
            else:
                # Convert other types to string safely
                value = str(value)[:1024]

            sanitized[key] = value

        return sanitized

    def _validate_timestamp(self, timestamp: str) -> bool:
        """Validate timestamp to prevent replay attacks"""
        try:
            ts = int(timestamp)
            current_time = int(time.time())

            # Allow 5 minute skew for clock differences
            max_skew = 300

            if abs(current_time - ts) > max_skew:
                logger.warning(f"Timestamp outside acceptable range: {timestamp}")
                return False

            return True
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp format: {timestamp}")
            return False

    def _rate_limit_check(self, user_id: str) -> bool:
        """Basic rate limiting per user"""
        current_time = time.time()

        # Clean up old entries (older than 1 minute)
        self._rate_limits = {
            uid: (requests, last_time) for uid, (requests, last_time) in self._rate_limits.items()
            if current_time - last_time < 60
        }

        # Check current user's rate
        if user_id in self._rate_limits:
            request_count, last_request_time = self._rate_limits[user_id]
            if current_time - last_request_time < 60:  # Within 1 minute window
                if request_count > 1000:  # Max 1000 requests per minute per user
                    logger.warning(f"Rate limit exceeded for user: {user_id}")
                    return False
                self._rate_limits[user_id] = (request_count + 1, current_time)
            else:
                self._rate_limits[user_id] = (1, current_time)
        else:
            self._rate_limits[user_id] = (1, current_time)

        return True

    def _cleanup_old_stats(self):
        """Cleanup old statistics to prevent memory bloat"""
        with self._stats_lock:
            # Limit unique users tracking
            if len(self.stats['unique_users']) > self.MAX_UNIQUE_USERS_TRACKED:
                # Convert to list, keep most recent, convert back to set
                users_list = list(self.stats['unique_users'])
                self.stats['unique_users'] = set(users_list[-self.MAX_UNIQUE_USERS_TRACKED:])
                logger.info(f"Cleaned up old user stats, keeping {self.MAX_UNIQUE_USERS_TRACKED} most recent")

            # Limit unique flags tracking
            if len(self.stats['unique_flags_accessed']) > self.MAX_UNIQUE_FLAGS_TRACKED:
                flags_list = list(self.stats['unique_flags_accessed'])
                self.stats['unique_flags_accessed'] = set(flags_list[-self.MAX_UNIQUE_FLAGS_TRACKED:])
                logger.info(f"Cleaned up old flag stats, keeping {self.MAX_UNIQUE_FLAGS_TRACKED} most recent")

    def _get_headers(self, payload: str = "") -> Dict[str, str]:
        """Get headers with FeatureFlagsHQ HMAC authentication and enhanced security"""
        timestamp = str(int(time.time()))
        signature, _ = generate_featureflagshq_signature(
            self.client_id, self.client_secret, payload, timestamp
        )

        headers = {
            'Content-Type': 'application/json',
            'X-SDK-Provider': BRAND_NAME,
            'X-Client-ID': self.client_id,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
            'X-Session-ID': self.session_id,
            'X-SDK-Version': __version__,
            'X-Environment': self.environment,
            'User-Agent': f'{BRAND_NAME}-Python-SDK/{__version__}',
            **self.custom_headers
        }

        # Never log sensitive headers in debug mode
        if logger.isEnabledFor(logging.DEBUG):
            safe_headers = {k: v for k, v in headers.items()
                            if k not in self.SENSITIVE_HEADERS}
            logger.debug(f"Request headers (sanitized): {safe_headers}")

        return headers

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows API calls"""
        if self._circuit_breaker['state'] == 'open':
            # If last_failure_time is None, circuit breaker should remain open
            if (self._circuit_breaker['last_failure_time'] is not None and
                    (time.time() - self._circuit_breaker['last_failure_time']) > self._circuit_breaker[
                        'recovery_timeout']):
                self._circuit_breaker['state'] = 'half-open'
                logger.info("FeatureFlagsHQ: Circuit breaker moved to half-open state")
                return True
            return False
        return True

    def _record_api_success(self):
        """Record successful API call"""
        with self._stats_lock:
            self.stats['api_calls']['successful'] += 1
            self.stats['api_calls']['total'] += 1

        if self._circuit_breaker['state'] == 'half-open':
            self._circuit_breaker['state'] = 'closed'
            self._circuit_breaker['failure_count'] = 0
            logger.info("FeatureFlagsHQ: Circuit breaker closed after successful call")

    def _record_api_failure(self, error_type: str = 'other_errors'):
        """Record API failure and update circuit breaker"""
        with self._stats_lock:
            self.stats['api_calls']['failed'] += 1
            self.stats['api_calls']['total'] += 1
            self.stats['errors'][error_type] += 1

        self._circuit_breaker['failure_count'] += 1
        self._circuit_breaker['last_failure_time'] = time.time()

        if self._circuit_breaker['failure_count'] >= self._circuit_breaker['failure_threshold']:
            self._circuit_breaker['state'] = 'open'
            logger.warning("FeatureFlagsHQ: Circuit breaker opened due to repeated failures")

    def _fetch_flags(self) -> Dict[str, FeatureFlagsHQFlag]:
        """Fetch feature flags from FeatureFlagsHQ API"""
        if not self._check_circuit_breaker():
            logger.debug("FeatureFlagsHQ: API call blocked by circuit breaker")
            return {}

        flags_url = f"{self.api_base_url.rstrip('/')}/v1/flags/"

        try:
            headers = self._get_headers("")
            response = self.session.get(
                flags_url,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 401:
                self._record_api_failure('auth_errors')
                raise FeatureFlagsHQAuthError("Invalid credentials")

            response.raise_for_status()
            self._record_api_success()

            response_data = response.json()

            # Store environment info
            if 'environment' in response_data:
                self.environment_info = response_data['environment']
                self.environment_info['provider'] = BRAND_NAME

            # Parse feature flags
            flags = {}
            if 'data' in response_data:
                for flag_data in response_data['data']:
                    try:
                        flag = FeatureFlagsHQFlag.from_dict(flag_data)
                        flags[flag.name] = flag
                    except FeatureFlagsHQConfigError as e:
                        logger.error(f"FeatureFlagsHQ: Invalid flag data: {e}")
                        continue

            logger.info(f"FeatureFlagsHQ: Fetched {len(flags)} feature flags")
            return flags

        except requests.exceptions.Timeout:
            self._record_api_failure('network_errors')
            raise FeatureFlagsHQTimeoutError("Request timeout")
        except requests.exceptions.ConnectionError:
            self._record_api_failure('network_errors')
            raise FeatureFlagsHQNetworkError("Connection error")
        except requests.RequestException as e:
            self._record_api_failure('network_errors')
            logger.error(f"FeatureFlagsHQ: Failed to fetch feature flags: {e}")
            return {}

    def _initial_fetch(self):
        """Initial fetch of feature flags"""
        try:
            new_flags = self._fetch_flags()
            with self._flags_lock:
                self.feature_flags = new_flags
            self.stats['last_sync'] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.error(f"FeatureFlagsHQ: Initial fetch failed: {e}")
            if not isinstance(e, (FeatureFlagsHQError,)):
                self._record_api_failure()

    def _start_background_tasks(self):
        """Start background threads"""
        if self.offline_mode:
            return

        # Polling thread
        self._polling_thread = threading.Thread(
            target=self._polling_worker,
            daemon=True,
            name="FeatureFlagsHQ-Polling"
        )
        self._polling_thread.start()

        # Log upload thread
        if self.enable_metrics:
            self._log_upload_thread = threading.Thread(
                target=self._log_upload_worker,
                daemon=True,
                name="FeatureFlagsHQ-LogUpload"
            )
            self._log_upload_thread.start()

        logger.info("FeatureFlagsHQ: Background tasks started")

    def _polling_worker(self):
        """Background worker for polling flag updates"""
        while not self._stop_event.wait(self.polling_interval):
            try:
                old_flags = dict(self.feature_flags)
                new_flags = self._fetch_flags()

                if new_flags:
                    with self._flags_lock:
                        # Detect changes for callbacks
                        if self.on_flag_change:
                            for flag_name, new_flag in new_flags.items():
                                old_flag = old_flags.get(flag_name)
                                if not old_flag or old_flag.value != new_flag.value:
                                    try:
                                        old_value = old_flag.value if old_flag else None
                                        self.on_flag_change(flag_name, old_value, new_flag.value)
                                    except Exception as e:
                                        logger.error(f"Error in flag change callback: {e}")

                        self.feature_flags.update(new_flags)

                    self.stats['last_sync'] = datetime.now(timezone.utc).isoformat()
                    logger.debug("FeatureFlagsHQ: Flags updated from polling")

            except Exception as e:
                logger.error(f"FeatureFlagsHQ: Error in polling worker: {e}")

    def _log_upload_worker(self):
        """Background worker for uploading logs"""
        while not self._stop_event.wait(self.log_upload_interval):
            try:
                self._upload_user_logs()
            except Exception as e:
                logger.error(f"FeatureFlagsHQ: Error in log upload worker: {e}")

    def _upload_user_logs(self):
        """Upload user logs to API"""
        if self.user_access_logs.empty() or not self._check_circuit_breaker():
            return

        logs_batch = []
        while not self.user_access_logs.empty() and len(logs_batch) < self.max_logs_batch:
            try:
                log_entry = self.user_access_logs.get_nowait()
                logs_batch.append(asdict(log_entry))
            except Empty:
                break

        if not logs_batch:
            return

        upload_url = f"{self.api_base_url.rstrip('/')}/v1/logs/batch/"
        payload = {
            'logs': logs_batch,
            'session_metadata': {
                'session_id': self.session_id,
                'environment': self.environment_info,
                'system_info': asdict(self.system_metadata),
                'provider': BRAND_NAME,
                'stats': self._get_stats_snapshot()
            }
        }

        try:
            payload_str = json.dumps(payload)
            headers = self._get_headers(payload_str)

            response = self.session.post(
                upload_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            self._record_api_success()

            self.stats['last_log_upload'] = datetime.now(timezone.utc).isoformat()
            logger.debug(f"FeatureFlagsHQ: Uploaded {len(logs_batch)} log entries")

        except Exception as e:
            self._record_api_failure()
            logger.error(f"FeatureFlagsHQ: Failed to upload logs: {e}")
            # Put logs back for retry
            for log_data in logs_batch:
                try:
                    log_entry = FeatureFlagsHQUserAccessLog(**log_data)
                    self.user_access_logs.put(log_entry)
                except Exception:
                    pass

    def _get_stats_snapshot(self) -> Dict:
        """Get thread-safe stats snapshot"""
        with self._stats_lock:
            timing_stats = self.stats['evaluation_times'].copy()
            if timing_stats['count'] == 0:
                timing_stats['min_ms'] = 0.0
                timing_stats['avg_ms'] = 0.0

            return {
                'total_user_accesses': self.stats['total_user_accesses'],
                'unique_users_count': len(self.stats['unique_users']),
                'unique_flags_count': len(self.stats['unique_flags_accessed']),
                'segment_matches': self.stats['segment_matches'],
                'rollout_evaluations': self.stats['rollout_evaluations'],
                'evaluation_times': timing_stats,
                'api_calls': self.stats['api_calls'].copy(),
                'errors': self.stats['errors'].copy(),
                'last_sync': self.stats['last_sync'],
                'sdk_provider': BRAND_NAME,
                'sdk_version': __version__
            }

    def _update_timing_stats(self, evaluation_time_ms: float):
        """Update timing statistics thread-safely"""
        with self._stats_lock:
            timing_stats = self.stats['evaluation_times']
            timing_stats['total_ms'] += evaluation_time_ms
            timing_stats['count'] += 1
            timing_stats['min_ms'] = min(timing_stats['min_ms'], evaluation_time_ms)
            timing_stats['max_ms'] = max(timing_stats['max_ms'], evaluation_time_ms)
            timing_stats['avg_ms'] = timing_stats['total_ms'] / timing_stats['count']

    def _log_user_access(
            self,
            user_id: str,
            flag_key: str,
            flag_value: Any,
            flag_type: str,
            segments: Optional[Dict[str, Any]],
            evaluation_context: Dict[str, Any]
    ):
        """Log user access if metrics are enabled"""
        if not self.enable_metrics:
            return

        evaluation_time_ms = evaluation_context.get('evaluation_time_ms', 0.0)

        log_entry = FeatureFlagsHQUserAccessLog(
            user_id=user_id,
            flag_key=flag_key,
            flag_value=flag_value,
            flag_type=flag_type,
            segments=segments,
            evaluation_context=evaluation_context,
            evaluation_time_ms=evaluation_time_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=self.session_id,
            request_id="",  # Generated in __post_init__
            sdk_provider=BRAND_NAME,
            sdk_version=__version__,
            metadata={
                'environment': self.environment_info.get('name', 'Unknown'),
                'provider': BRAND_NAME
            }
        )

        # Queue log entry (non-blocking)
        try:
            self.user_access_logs.put(log_entry, block=False)
        except:
            # If queue is full, drop oldest entries to prevent memory issues
            try:
                self.user_access_logs.get_nowait()
                self.user_access_logs.put(log_entry, block=False)
            except:
                pass

        # Update statistics
        with self._stats_lock:
            self.stats['total_user_accesses'] += 1
            self.stats['unique_users'].add(user_id)
            self.stats['unique_flags_accessed'].add(flag_key)

            if evaluation_time_ms > 0:
                self._update_timing_stats(evaluation_time_ms)

            if evaluation_context.get('segments_matched'):
                self.stats['segment_matches'] += 1
            if evaluation_context.get('rollout_qualified') is not None:
                self.stats['rollout_evaluations'] += 1

    def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events for monitoring"""
        security_event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'details': sanitize_log_data(details),
            'session_id': self.session_id
        }

        # In production, this would be sent to a security monitoring system
        logger.warning(f"Security event: {event_type} - {sanitize_log_data(details)}")

    def get(
            self,
            user_id: str,
            flag_key: str,
            default_value: Any = None,
            segments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Secure version of get method with enhanced validation"""

        # Input validation and sanitization
        try:
            user_id = self._validate_user_id(user_id)
            flag_key = self._validate_flag_key(flag_key)
            segments = self._sanitize_segments(segments)
        except FeatureFlagsHQError as e:
            self._security_stats['invalid_input_attempts'] += 1
            self._log_security_event('invalid_input', {
                'user_id': str(user_id)[:50] if user_id else None,
                'flag_key': str(flag_key)[:50] if flag_key else None,
                'error': str(e)
            })
            raise

        # Rate limiting
        if not self._rate_limit_check(user_id):
            self._security_stats['blocked_malicious_requests'] += 1
            logger.warning(f"Request blocked due to rate limiting: {user_id}")
            return default_value

        # Memory monitoring
        self._memory_monitor.check_memory_usage(self)

        # Cleanup stats periodically
        if self.stats['total_user_accesses'] % 1000 == 0:
            self._cleanup_old_stats()

        with measure_time() as get_total_time:
            # Thread-safe flag access
            with self._flags_lock:
                flag = self.feature_flags.get(flag_key)

            if not flag:
                total_time_ms = round(get_total_time(), 3)
                logger.debug(f"FeatureFlagsHQ: Flag '{flag_key}' not found")

                self._log_user_access(
                    user_id=user_id,
                    flag_key=flag_key,
                    flag_value=default_value,
                    flag_type="unknown",
                    segments=segments,
                    evaluation_context={
                        'flag_found': False,
                        'default_value_used': True,
                        'evaluation_reason': 'flag_not_found',
                        'evaluation_time_ms': total_time_ms,
                        'provider': BRAND_NAME
                    }
                )
                return default_value

            # Evaluate flag for user
            try:
                flag_value, evaluation_context = flag.evaluate_for_user(user_id, segments)

                # Use custom default if flag evaluation returned default
                if evaluation_context.get('default_value_used') and default_value is not None:
                    flag_value = default_value

                # Add total SDK time to context
                total_time_ms = round(get_total_time(), 3)
                evaluation_context['total_sdk_time_ms'] = total_time_ms
                evaluation_context['provider'] = BRAND_NAME

                # Log the access
                self._log_user_access(
                    user_id=user_id,
                    flag_key=flag_key,
                    flag_value=flag_value,
                    flag_type=flag.type,
                    segments=segments,
                    evaluation_context=evaluation_context
                )

                return flag_value

            except Exception as e:
                logger.error(f"FeatureFlagsHQ: Error evaluating flag '{flag_key}': {e}")
                return default_value

    # Convenience methods with type safety
    def get_bool(self, user_id: str, flag_key: str, default_value: bool = False,
                 segments: Optional[Dict[str, Any]] = None) -> bool:
        """Get boolean feature flag value"""
        value = self.get(user_id, flag_key, default_value, segments)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value) if value is not None else bool(default_value)

    def get_string(self, user_id: str, flag_key: str, default_value: str = "",
                   segments: Optional[Dict[str, Any]] = None) -> str:
        """Get string feature flag value"""
        value = self.get(user_id, flag_key, default_value, segments)
        return str(value) if value is not None else str(default_value)

    def get_int(self, user_id: str, flag_key: str, default_value: int = 0,
                segments: Optional[Dict[str, Any]] = None) -> int:
        """Get integer feature flag value"""
        value = self.get(user_id, flag_key, default_value, segments)
        try:
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                return int(float(value))
            return int(default_value)
        except (ValueError, TypeError):
            return int(default_value)

    def get_float(self, user_id: str, flag_key: str, default_value: float = 0.0,
                  segments: Optional[Dict[str, Any]] = None) -> float:
        """Get float feature flag value"""
        value = self.get(user_id, flag_key, default_value, segments)
        try:
            # If the value is the typed default (0.0) and user provided a different default,
            # check if this was due to conversion failure by getting the raw flag value
            if value == 0.0 and default_value != 0.0:
                # Get the flag to check its raw value
                with self._flags_lock:
                    flag = self.feature_flags.get(flag_key)
                if flag and flag.is_active:
                    # Try to convert the raw value ourselves
                    try:
                        return float(flag.value) if flag.value is not None else float(default_value)
                    except (ValueError, TypeError):
                        return float(default_value)

            return float(value) if value is not None else float(default_value)
        except (ValueError, TypeError):
            return float(default_value)

    def get_json(self, user_id: str, flag_key: str, default_value: Any = None,
                 segments: Optional[Dict[str, Any]] = None) -> Any:
        """Get JSON feature flag value"""
        if default_value is None:
            default_value = {}

        value = self.get(user_id, flag_key, default_value, segments)

        # Check if value is the typed default ({}) and user provided a different default
        if isinstance(value, dict) and value == {} and default_value != {}:
            # Get the flag to check its raw value
            with self._flags_lock:
                flag = self.feature_flags.get(flag_key)
            if flag and flag.is_active:
                # Try to convert the raw value ourselves
                try:
                    if isinstance(flag.value, str):
                        return json.loads(flag.value)
                    return flag.value
                except (json.JSONDecodeError, AttributeError):
                    return default_value

        # Handle already parsed values
        if not isinstance(value, str):
            return value

        # Parse string values
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default_value

        return default_value

    def is_flag_enabled_for_user(self, user_id: str, flag_key: str, segments: Optional[Dict[str, Any]] = None) -> bool:
        """Check if a feature flag is enabled for a specific user"""
        return self.get_bool(user_id, flag_key, False, segments)

    def get_user_flags(self, user_id: str, segments: Optional[Dict[str, Any]] = None,
                       flag_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get multiple feature flags evaluated for a specific user"""
        if not user_id:
            raise FeatureFlagsHQError("user_id is required")

        # Validate user_id first
        user_id = self._validate_user_id(user_id)
        segments = self._sanitize_segments(segments)

        user_flags = {}

        with self._flags_lock:
            flags_to_evaluate = self.feature_flags
            if flag_keys:
                # Validate all flag keys first
                validated_keys = []
                for key in flag_keys:
                    try:
                        validated_keys.append(self._validate_flag_key(key))
                    except FeatureFlagsHQError:
                        continue
                flags_to_evaluate = {k: v for k, v in self.feature_flags.items() if k in validated_keys}

        for flag_key, flag in flags_to_evaluate.items():
            try:
                flag_value, _ = flag.evaluate_for_user(user_id, segments)
                user_flags[flag_key] = flag_value
            except Exception as e:
                logger.error(f"Error evaluating flag {flag_key} for user {user_id}: {e}")
                user_flags[flag_key] = flag._get_typed_default_value()

        return user_flags

    def refresh_flags(self) -> bool:
        """Manually refresh feature flags from API"""
        if self.offline_mode:
            logger.warning("FeatureFlagsHQ: Cannot refresh flags in offline mode")
            return False

        try:
            new_flags = self._fetch_flags()
            if new_flags:
                with self._flags_lock:
                    self.feature_flags.update(new_flags)
                self.stats['last_sync'] = datetime.now(timezone.utc).isoformat()
                logger.info("FeatureFlagsHQ: Feature flags manually refreshed")
                return True
            return False
        except Exception as e:
            logger.error(f"FeatureFlagsHQ: Manual refresh failed: {e}")
            return False

    def get_all_flags(self) -> Dict[str, Dict]:
        """Get all cached feature flags with their configuration"""
        with self._flags_lock:
            return {
                flag_key: {
                    'name': flag.name,
                    'type': flag.type,
                    'value': flag.value,
                    'is_active': flag.is_active,
                    'segments_count': len(flag.segments) if flag.segments else 0,
                    'rollout_percentage': flag.rollout.percentage,
                    'version': flag.version,
                    'updated_at': flag.updated_at,
                    'provider': BRAND_NAME
                }
                for flag_key, flag in self.feature_flags.items()
            }

    def get_stats(self) -> Dict:
        """Get comprehensive SDK usage statistics"""
        return {
            **self._get_stats_snapshot(),
            'session_id': self.session_id,
            'environment': self.environment_info,
            'cached_flags_count': len(self.feature_flags),
            'pending_user_logs': self.user_access_logs.qsize(),
            'circuit_breaker': {
                'state': self._circuit_breaker['state'],
                'failure_count': self._circuit_breaker['failure_count']
            },
            'configuration': {
                'polling_interval': self.polling_interval,
                'log_upload_interval': self.log_upload_interval,
                'offline_mode': self.offline_mode,
                'enable_metrics': self.enable_metrics,
                'environment': self.environment
            }
        }

    def get_security_stats(self) -> Dict[str, Any]:
        """Get security-related statistics"""
        return {
            **self._security_stats,
            'rate_limited_users': len(self._rate_limits),
            'timestamp': time.time()
        }

    def flush_logs(self) -> bool:
        """Manually flush all pending user logs"""
        if self.offline_mode or not self.enable_metrics:
            logger.warning("FeatureFlagsHQ: Cannot flush logs in offline mode or with metrics disabled")
            return False

        try:
            self._upload_user_logs()
            logger.info("FeatureFlagsHQ: User logs manually flushed")
            return True
        except Exception as e:
            logger.error(f"FeatureFlagsHQ: Manual log flush failed: {e}")
            return False

    def get_health_check(self) -> Dict[str, Any]:
        """Get comprehensive SDK health status"""
        with self._flags_lock:
            cached_flags_count = len(self.feature_flags)

        return {
            'status': 'healthy' if self._circuit_breaker['state'] != 'open' else 'degraded',
            'provider': BRAND_NAME,
            'sdk_version': __version__,
            'api_base_url': self.api_base_url,
            'cached_flags_count': cached_flags_count,
            'session_id': self.session_id,
            'environment': self.environment,
            'offline_mode': self.offline_mode,
            'last_sync': self.stats['last_sync'],
            'circuit_breaker': {
                'state': self._circuit_breaker['state'],
                'failure_count': self._circuit_breaker['failure_count']
            },
            'system_info': {
                'sdk_version': self.system_metadata.sdk_version,
                'python_version': self.system_metadata.python_version,
                'platform': self.system_metadata.platform
            },
            'security_stats': self.get_security_stats()
        }

    def shutdown(self):
        """Gracefully shutdown the FeatureFlagsHQ SDK"""
        logger.info("FeatureFlagsHQ: Initiating SDK shutdown...")

        # Signal all threads to stop
        self._stop_event.set()

        # Upload any remaining logs
        if self.enable_metrics and not self.offline_mode:
            try:
                self._upload_user_logs()
                logger.debug("FeatureFlagsHQ: Final log upload completed")
            except Exception as e:
                logger.warning(f"FeatureFlagsHQ: Error during final log upload: {e}")

        # Wait for background threads to finish
        threads_to_join = [
            (self._polling_thread, "Polling"),
            (self._log_upload_thread, "LogUpload")
        ]

        for thread, name in threads_to_join:
            if thread and thread.is_alive():
                logger.debug(f"FeatureFlagsHQ: Waiting for {name} thread to finish...")
                thread.join(timeout=10)
                if thread.is_alive():
                    logger.warning(f"FeatureFlagsHQ: {name} thread did not shut down gracefully")

        # Close HTTP session
        try:
            self.session.close()
        except Exception as e:
            logger.warning(f"FeatureFlagsHQ: Error closing HTTP session: {e}")

        logger.info("FeatureFlagsHQ: SDK shutdown complete")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures proper cleanup"""
        self.shutdown()

    def __del__(self):
        """Destructor - ensures resources are cleaned up"""
        try:
            if hasattr(self, '_stop_event') and not self._stop_event.is_set():
                self.shutdown()
        except Exception:
            pass


# Configuration validation utilities
def validate_production_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration for production deployment"""
    warnings = []

    # Check for development settings in production
    if config.get('debug', False):
        warnings.append("Debug mode is enabled - disable for production")

    if config.get('api_base_url', '').startswith('http://'):
        warnings.append("Using HTTP instead of HTTPS - security risk")

    if config.get('timeout', 30) < 5:
        warnings.append("Timeout too low - may cause instability")

    if config.get('max_retries', 3) > 10:
        warnings.append("Max retries too high - may cause delays")

    if not config.get('client_secret', ''):
        warnings.append("Missing client secret")

    # Check for weak credentials (in development)
    client_secret = config.get('client_secret', '')
    if len(client_secret) < 32:
        warnings.append("Client secret appears to be weak")

    return warnings


def create_production_client(client_id: str, client_secret: str, environment: str, **kwargs) -> FeatureFlagsHQSDK:
    """Create a production-ready SDK instance with security hardening"""

    # Default secure configuration
    secure_config = {
        'timeout': 30,
        'max_retries': 3,
        'backoff_factor': 0.3,
        'debug': False,
        'enable_metrics': True,
        'polling_interval': 300,  # 5 minutes
        'log_upload_interval': 120,  # 2 minutes
        **kwargs
    }

    # Validate configuration
    warnings = validate_production_config(secure_config)
    if warnings:
        for warning in warnings:
            logger.warning(f"Configuration warning: {warning}")

    # Create SDK instance
    sdk = FeatureFlagsHQSDK(
        client_id=client_id,
        client_secret=client_secret,
        environment=environment,
        **secure_config
    )

    logger.info("Secure FeatureFlagsHQ SDK initialized with production configuration")

    return sdk
