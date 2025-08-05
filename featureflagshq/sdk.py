"""
FeatureFlagsHQ SDK - Core functionality with Enhanced Logging
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import Any, Dict, Optional, List, Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import SDK constants
try:
    from . import SDK_VERSION, DEFAULT_API_BASE_URL, USER_AGENT_PREFIX, COMPANY_NAME
except ImportError:
    # Fallback for direct execution
    SDK_VERSION = "1.0.0"
    DEFAULT_API_BASE_URL = "https://api.featureflagshq.com"
    COMPANY_NAME = "FeatureFlagsHQ"
    USER_AGENT_PREFIX = f"{COMPANY_NAME}-Python-SDK"

# Constants
MAX_USER_ID_LENGTH = 255
MAX_FLAG_NAME_LENGTH = 255
POLLING_INTERVAL = 300  # 5 minutes
LOG_UPLOAD_INTERVAL = 120  # 2 minutes
MAX_UNIQUE_USERS_TRACKED = 10000
MAX_UNIQUE_FLAGS_TRACKED = 1000
ENABLE_LOGGING = False


# Setup logging with security filter
class SecurityFilter(logging.Filter):
    """Filter to prevent sensitive data from being logged"""
    SENSITIVE_PATTERNS = [
        re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE),
        re.compile(r'signature["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE),
    ]

    def filter(self, record):
        if hasattr(record, 'msg'):
            message = str(record.msg)
            for pattern in self.SENSITIVE_PATTERNS:
                message = pattern.sub(r'\1[REDACTED]', message)
            record.msg = message
        return True


logger = logging.getLogger('featureflagshq_sdk2')
if ENABLE_LOGGING and not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    handler.addFilter(SecurityFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FeatureFlagsHQSDK:
    """Enhanced Feature Flag SDK with security and missing features"""

    def __init__(self, client_id: str = None, client_secret: str = None,
                 api_base_url: str = DEFAULT_API_BASE_URL,
                 environment: str = None, timeout: int = 30, max_retries: int = 3,
                 offline_mode: bool = False, enable_metrics: bool = True,
                 on_flag_change: Optional[Callable[[str, Any, Any], None]] = None):

        # Get credentials from environment if not provided
        if not client_id:
            client_id = os.getenv('FEATUREFLAGSHQ_CLIENT_ID') or os.getenv('FEATUREFLAGSHQ_CLIENT_KEY')
        if not client_secret:
            client_secret = os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET')
        if not environment:
            environment = os.getenv('FEATUREFLAGSHQ_ENVIRONMENT', 'production')

        # Validate inputs
        if not client_id or not client_secret:
            raise ValueError("client_id and client_secret are required")

        self.client_id = self._validate_string(client_id, "client_id")
        self.client_secret = self._validate_string(client_secret, "client_secret")
        self.api_base_url = self._validate_url(api_base_url)
        self.environment = self._validate_string(environment, "environment")
        self.timeout = timeout
        self.max_retries = max_retries
        self.offline_mode = offline_mode
        self.enable_metrics = enable_metrics
        self.on_flag_change = on_flag_change

        # Internal state
        self.flags = {}  # flag_name -> flag_data
        self.session_id = str(uuid.uuid4())
        self.logs_queue = Queue()
        self._lock = threading.RLock()
        self._stats_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._initialization_complete = threading.Event()

        # Enhanced statistics for session metadata
        self.stats = {
            'total_user_accesses': 0,
            'unique_users': set(),
            'unique_flags_accessed': set(),
            'last_sync': None,
            'last_log_upload': None,
            'api_calls': {'successful': 0, 'failed': 0, 'total': 0},
            'errors': {'network_errors': 0, 'auth_errors': 0, 'other_errors': 0},
            'segment_matches': 0,
            'rollout_evaluations': 0,
            'evaluation_times': {'total_ms': 0, 'count': 0, 'min_ms': float('inf'), 'max_ms': 0}
        }

        # Circuit breaker for API calls
        self._circuit_breaker = {
            'failure_count': 0,
            'last_failure_time': None,
            'state': 'closed',  # closed, open, half-open
            'failure_threshold': 5,
            'recovery_timeout': 60
        }

        # Rate limiting
        self._rate_limits = {}

        # Background threads
        self._polling_thread = None
        self._log_upload_thread = None

        # Session for HTTP requests
        self.session = requests.Session()
        self.session.timeout = timeout

        # Add retry adapter
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # System info for session metadata
        self._system_info = self._get_system_info()

        # Start SDK
        self._initialize()

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for session metadata"""
        try:
            import psutil
            memory_total = psutil.virtual_memory().total
            cpu_count = psutil.cpu_count()
        except ImportError:
            memory_total = None
            cpu_count = os.cpu_count()

        return {
            'platform': platform.system(),
            'python_version': platform.python_version(),
            'hostname': platform.node(),
            'process_id': os.getpid(),
            'cpu_count': cpu_count,
            'memory_total': memory_total
        }

    def _validate_url(self, url: str) -> str:
        """Validate and sanitize URL"""
        if not url or not isinstance(url, str):
            raise ValueError("API base URL must be a non-empty string")

        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            raise ValueError("Invalid URL scheme. Only http and https are allowed")

        if not parsed.netloc:
            raise ValueError("Invalid URL: missing hostname")

        return url.rstrip('/')

    def _validate_string(self, value: str, field_name: str, max_length: int = 255) -> str:
        """Validate and sanitize string inputs"""
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")

        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} cannot be empty")

        if len(value) > max_length:
            raise ValueError(f"{field_name} too long (max {max_length} characters)")

        # Remove control characters and dangerous patterns
        dangerous_chars = ['\n', '\r', '\0', '\t', '\x1b']
        for char in dangerous_chars:
            if char in value:
                raise ValueError(f"{field_name} contains invalid characters")

        # SQL injection prevention - basic patterns
        sql_patterns = ['--', ';', '/*', '*/', 'union', 'select', 'insert', 'delete', 'update', 'drop']
        value_lower = value.lower()
        for pattern in sql_patterns:
            if pattern in value_lower:
                raise ValueError(f"{field_name} contains potentially dangerous content")

        return value

    def _validate_user_id(self, user_id: str) -> str:
        """Enhanced user ID validation"""
        if user_id is None:
            raise ValueError("user_id cannot be None")

        user_id = self._validate_string(user_id, "user_id", MAX_USER_ID_LENGTH)

        # Additional pattern validation for user IDs
        if not re.match(r'^[a-zA-Z0-9_@\.\-\+]+$', user_id):
            if ENABLE_LOGGING: logger.warning(f"Potentially unsafe user_id pattern: {user_id[:50]}...")

        return user_id

    def _validate_flag_name(self, flag_name: str) -> str:
        """Enhanced flag name validation"""
        if flag_name is None:
            raise ValueError("flag_name cannot be None")

        flag_name = self._validate_string(flag_name, "flag_name", MAX_FLAG_NAME_LENGTH)

        # Flag names should be alphanumeric + underscores/hyphens
        if not re.match(r'^[a-zA-Z0-9_\-]+$', flag_name):
            raise ValueError("flag_name contains invalid characters")

        return flag_name

    def _rate_limit_check(self, user_id: str) -> bool:
        """Basic rate limiting per user"""
        if self.offline_mode:
            return True

        current_time = time.time()

        # Clean up old entries
        self._rate_limits = {
            uid: (count, last_time) for uid, (count, last_time) in self._rate_limits.items()
            if current_time - last_time < 60
        }

        # Check current user's rate
        if user_id in self._rate_limits:
            count, last_time = self._rate_limits[user_id]
            if current_time - last_time < 60:
                if count > 1000:  # Max 1000 requests per minute per user
                    if ENABLE_LOGGING: logger.warning(f"Rate limit exceeded for user: {user_id}")
                    return False
                self._rate_limits[user_id] = (count + 1, current_time)
            else:
                self._rate_limits[user_id] = (1, current_time)
        else:
            self._rate_limits[user_id] = (1, current_time)

        return True

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows API calls"""
        if self._circuit_breaker['state'] == 'open':
            if (self._circuit_breaker['last_failure_time'] and
                    (time.time() - self._circuit_breaker['last_failure_time']) > self._circuit_breaker[
                        'recovery_timeout']):
                self._circuit_breaker['state'] = 'half-open'
                if ENABLE_LOGGING: logger.info("Circuit breaker moved to half-open state")
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
            if ENABLE_LOGGING: logger.info("Circuit breaker closed after successful call")

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
            if ENABLE_LOGGING: logger.warning("Circuit breaker opened due to repeated failures")

    def _cleanup_old_stats(self):
        """Cleanup old statistics to prevent memory bloat"""
        with self._stats_lock:
            if len(self.stats['unique_users']) > MAX_UNIQUE_USERS_TRACKED:
                users_list = list(self.stats['unique_users'])
                self.stats['unique_users'] = set(users_list[-MAX_UNIQUE_USERS_TRACKED:])
                if ENABLE_LOGGING: logger.info(
                    f"Cleaned up old user stats, keeping {MAX_UNIQUE_USERS_TRACKED} most recent")

            if len(self.stats['unique_flags_accessed']) > MAX_UNIQUE_FLAGS_TRACKED:
                flags_list = list(self.stats['unique_flags_accessed'])
                self.stats['unique_flags_accessed'] = set(flags_list[-MAX_UNIQUE_FLAGS_TRACKED:])
                if ENABLE_LOGGING: logger.info(
                    f"Cleaned up old flag stats, keeping {MAX_UNIQUE_FLAGS_TRACKED} most recent")

    def _generate_signature(self, payload: str, timestamp: str) -> str:
        """Generate HMAC signature for API authentication"""
        message = f"{self.client_id}:{timestamp}:{payload}"
        signature = hmac.new(
            self.client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, payload: str = "") -> Dict[str, str]:
        """Get headers for API requests"""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(payload, timestamp)

        return {
            'Content-Type': 'application/json',
            'X-SDK-Provider': COMPANY_NAME,
            'X-Client-ID': self.client_id,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
            'X-Session-ID': self.session_id,
            'X-SDK-Version': SDK_VERSION,
            'X-Environment': self.environment,
            'User-Agent': f'{USER_AGENT_PREFIX}/{SDK_VERSION}'
        }

    def _fetch_flags(self) -> Dict[str, Any]:
        """Fetch flags from server with circuit breaker"""
        if self.offline_mode or not self._check_circuit_breaker():
            return {}

        try:
            url = f"{self.api_base_url}/v1/flags/"
            headers = self._get_headers("")

            response = self.session.get(url, headers=headers)

            if response.status_code == 401:
                self._record_api_failure('auth_errors')
                if ENABLE_LOGGING: logger.error("Authentication failed - check credentials")
                return {}

            response.raise_for_status()
            self._record_api_success()

            data = response.json()
            flags = {}

            if 'data' in data and isinstance(data['data'], list):
                for flag_data in data['data']:
                    if isinstance(flag_data, dict) and 'name' in flag_data:
                        flag_name = flag_data['name']
                        if isinstance(flag_name, str) and flag_name:
                            flags[flag_name] = flag_data

            if ENABLE_LOGGING: logger.info(f"Fetched {len(flags)} flags from server")
            return flags

        except requests.exceptions.Timeout:
            self._record_api_failure('network_errors')
            if ENABLE_LOGGING: logger.warning("Request timeout during flag fetch")
            return {}
        except requests.exceptions.ConnectionError:
            self._record_api_failure('network_errors')
            if ENABLE_LOGGING: logger.warning("Connection error during flag fetch")
            return {}
        except Exception as e:
            self._record_api_failure()
            if ENABLE_LOGGING: logger.error(f"Failed to fetch flags: {e}")
            return {}

    def _evaluate_flag(self, flag_data: Dict[str, Any], user_id: str,
                       segments: Optional[Dict[str, Any]] = None) -> tuple:
        """Evaluate flag for user and return (value, evaluation_context)"""
        start_time = time.time()

        evaluation_context = {
            'flag_active': flag_data.get('is_active', True),
            'flag_found': True,
            'default_value_used': False,
            'segments_matched': [],
            'segments_evaluated': [],
            'rollout_qualified': False,
            'reason': 'active_flag'
        }

        if not flag_data.get('is_active', True):
            evaluation_context['default_value_used'] = True
            evaluation_context['reason'] = 'flag_inactive'
            value = self._get_default_value(flag_data.get('type', 'string'))
            evaluation_time = (time.time() - start_time) * 1000
            evaluation_context['total_sdk_time_ms'] = evaluation_time
            return value, evaluation_context

        # Check segments if provided
        if segments and flag_data.get('segments'):
            segments_matched = []
            segments_evaluated = []

            for segment in flag_data['segments']:
                segment_name = segment.get('name', '')
                segments_evaluated.append(segment_name)

                if self._check_segment_match(segment, segments):
                    segments_matched.append(segment_name)

            evaluation_context['segments_matched'] = segments_matched
            evaluation_context['segments_evaluated'] = segments_evaluated

            # Update stats
            with self._stats_lock:
                self.stats['segment_matches'] += len(segments_matched)

            # If segments exist but none matched, return default
            if flag_data.get('segments') and not segments_matched:
                evaluation_context['default_value_used'] = True
                evaluation_context['reason'] = 'segment_not_matched'
                value = self._get_default_value(flag_data.get('type', 'string'))
                evaluation_time = (time.time() - start_time) * 1000
                evaluation_context['total_sdk_time_ms'] = evaluation_time
                return value, evaluation_context

        # Check rollout percentage
        rollout_percentage = flag_data.get('rollout', {}).get('percentage', 100)
        if rollout_percentage < 100:
            with self._stats_lock:
                self.stats['rollout_evaluations'] += 1

            user_hash = hashlib.sha256(f"{flag_data['name']}:{user_id}".encode()).hexdigest()
            user_percentage = int(user_hash[:8], 16) % 100

            if user_percentage < rollout_percentage:
                evaluation_context['rollout_qualified'] = True
                evaluation_context['reason'] = 'rollout_qualified'
            else:
                evaluation_context['default_value_used'] = True
                evaluation_context['reason'] = 'rollout_not_qualified'
                value = self._get_default_value(flag_data.get('type', 'string'))
                evaluation_time = (time.time() - start_time) * 1000
                evaluation_context['total_sdk_time_ms'] = evaluation_time
                return value, evaluation_context

        # Return flag value
        value = self._convert_value(flag_data.get('value'), flag_data.get('type', 'string'))
        evaluation_time = (time.time() - start_time) * 1000
        evaluation_context['total_sdk_time_ms'] = evaluation_time

        # Update evaluation time stats
        with self._stats_lock:
            eval_times = self.stats['evaluation_times']
            eval_times['total_ms'] += evaluation_time
            eval_times['count'] += 1
            eval_times['min_ms'] = min(eval_times['min_ms'], evaluation_time)
            eval_times['max_ms'] = max(eval_times['max_ms'], evaluation_time)

        return value, evaluation_context

    def _check_segment_match(self, segment: Dict, segments: Dict[str, Any]) -> bool:
        """Check if segment matches user attributes"""
        try:
            segment_name = segment.get('name')
            if not segment_name or segment_name not in segments:
                return False

            comparator = segment.get('comparator', '==')
            segment_value = segment.get('value')
            segment_type = segment.get('type', 'string')
            user_value = segments[segment_name]

            # Convert values to same type
            if segment_type == 'int':
                user_val = int(user_value)
                seg_val = int(segment_value)
            elif segment_type == 'float':
                user_val = float(user_value)
                seg_val = float(segment_value)
            elif segment_type == 'bool':
                user_val = bool(user_value)
                seg_val = str(segment_value).lower() == 'true'
            else:
                user_val = str(user_value)
                seg_val = str(segment_value)

            # Apply comparator
            if comparator == '==':
                return user_val == seg_val
            elif comparator == '!=':
                return user_val != seg_val
            elif comparator == '>':
                return user_val > seg_val
            elif comparator == '<':
                return user_val < seg_val
            elif comparator == '>=':
                return user_val >= seg_val
            elif comparator == '<=':
                return user_val <= seg_val
            elif comparator == 'contains':
                return seg_val in str(user_val)
            else:
                return False

        except (ValueError, TypeError):
            return False

    def _convert_value(self, value: Any, value_type: str) -> Any:
        """Convert string value to proper type"""
        try:
            if value_type == 'bool':
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ('true', '1', 'yes')
            elif value_type == 'int':
                return int(float(value))
            elif value_type == 'float':
                return float(value)
            elif value_type == 'json':
                if isinstance(value, (dict, list)):
                    return value
                return json.loads(str(value))
            else:
                return str(value)
        except (ValueError, json.JSONDecodeError):
            return self._get_default_value(value_type)

    def _get_default_value(self, value_type: str) -> Any:
        """Get default value for type"""
        defaults = {
            'bool': False,
            'int': 0,
            'float': 0.0,
            'json': {},
            'string': ''
        }
        return defaults.get(value_type, '')

    def _log_access(self, user_id: str, flag_name: str, flag_value: Any, evaluation_context: Dict,
                    evaluation_time_ms: float, segments: Optional[Dict] = None):
        """Log flag access for analytics with enhanced structure"""
        if not self.enable_metrics:
            return

        log_entry = {
            'user_id': user_id,
            'flag_name': flag_name,
            'flag_value': flag_value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'session_id': self.session_id,
            'evaluation_time_ms': evaluation_time_ms,
            'evaluation_context': evaluation_context,
            'segments': segments or {},
            'metadata': {
                'sdk_version': SDK_VERSION,
                'environment': self.environment
            }
        }

        try:
            self.logs_queue.put(log_entry, block=False)
        except:
            # Queue is full, ignore
            pass

        # Update statistics
        with self._stats_lock:
            self.stats['total_user_accesses'] += 1
            self.stats['unique_users'].add(user_id)
            self.stats['unique_flags_accessed'].add(flag_name)

        # Cleanup stats periodically
        if self.stats['total_user_accesses'] % 1000 == 0:
            self._cleanup_old_stats()

    def _get_session_metadata(self) -> Dict[str, Any]:
        """Get session metadata for log uploads"""
        with self._stats_lock:
            eval_times = self.stats['evaluation_times']
            avg_ms = (eval_times['total_ms'] / eval_times['count']) if eval_times['count'] > 0 else 0

            return {
                'session_id': self.session_id,
                'environment': {
                    'name': self.environment
                },
                'system_info': self._system_info,
                'stats': {
                    'total_user_accesses': self.stats['total_user_accesses'],
                    'unique_users_count': len(self.stats['unique_users']),
                    'unique_flags_count': len(self.stats['unique_flags_accessed']),
                    'segment_matches': self.stats['segment_matches'],
                    'rollout_evaluations': self.stats['rollout_evaluations'],
                    'evaluation_times': {
                        'avg_ms': avg_ms,
                        'min_ms': eval_times['min_ms'] if eval_times['min_ms'] != float('inf') else 0,
                        'max_ms': eval_times['max_ms'],
                        'total_ms': eval_times['total_ms'],
                        'count': eval_times['count']
                    }
                }
            }

    def _upload_logs(self):
        """Upload logs to server with session metadata"""
        if self.offline_mode or self.logs_queue.empty() or not self._check_circuit_breaker():
            return

        logs = []
        while not self.logs_queue.empty() and len(logs) < 100:
            try:
                logs.append(self.logs_queue.get_nowait())
            except Empty:
                break

        if not logs:
            return

        try:
            url = f"{self.api_base_url}/v1/logs/batch/"
            payload = {
                'logs': logs,
                'session_metadata': self._get_session_metadata()
            }
            payload_str = json.dumps(payload)
            headers = self._get_headers(payload_str)

            response = self.session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            self._record_api_success()

            self.stats['last_log_upload'] = datetime.now(timezone.utc).isoformat()
            logger.debug(f"Uploaded {len(logs)} log entries")

        except Exception as e:
            self._record_api_failure()
            if ENABLE_LOGGING: logger.error(f"Failed to upload logs: {e}")
            # Put logs back in queue for retry (limit to prevent memory bloat)
            if len(logs) <= 10:
                for log in logs:
                    try:
                        self.logs_queue.put(log, block=False)
                    except:
                        break

    def _polling_worker(self):
        """Background worker to poll for flag updates with change detection"""
        logger.debug("Polling worker started")
        try:
            # Check if we should stop immediately (for manual calls in tests)
            if self._stop_event.is_set():
                logger.debug("Stop event already set, exiting polling worker")
                return

            # Use shorter intervals for faster shutdown response
            poll_interval = min(POLLING_INTERVAL, 10)  # Max 10 seconds for testing
            while not self._stop_event.wait(poll_interval):
                # Check if we should stop before doing any work 
                if self._stop_event.is_set():
                    break

                try:
                    old_flags = dict(self.flags) if self.on_flag_change else {}
                    new_flags = self._fetch_flags()

                    if new_flags:
                        with self._lock:
                            # Detect changes for callbacks
                            if self.on_flag_change:
                                for flag_name, new_flag_data in new_flags.items():
                                    old_flag_data = old_flags.get(flag_name)
                                    old_value = old_flag_data.get('value') if old_flag_data else None
                                    new_value = new_flag_data.get('value')

                                    if old_value != new_value:
                                        try:
                                            self.on_flag_change(flag_name, old_value, new_value)
                                        except Exception as e:
                                            if ENABLE_LOGGING: logger.error(f"Error in flag change callback: {e}")

                            self.flags.update(new_flags)

                        self.stats['last_sync'] = datetime.now(timezone.utc).isoformat()
                        logger.debug("Updated flags from polling")
                except Exception as e:
                    if ENABLE_LOGGING: logger.error(f"Error in polling worker: {e}")
                    # Don't break the loop, continue with next iteration
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Fatal error in polling worker: {e}")
        finally:
            logger.debug("Polling worker stopped")

    def _log_upload_worker(self):
        """Background worker to upload logs"""
        logger.debug("Log upload worker started")
        try:
            # Use shorter intervals for faster shutdown response
            upload_interval = min(LOG_UPLOAD_INTERVAL, 5)  # Max 5 seconds for testing
            while not self._stop_event.wait(upload_interval):
                # Check if we should stop before doing any work
                if self._stop_event.is_set():
                    break

                try:
                    self._upload_logs()
                except Exception as e:
                    if ENABLE_LOGGING: logger.error(f"Error in log upload worker: {e}")
                    # Don't break the loop, continue with next iteration
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Fatal error in log upload worker: {e}")
        finally:
            logger.debug("Log upload worker stopped")

    def _initialize(self):
        """Initialize SDK"""
        try:
            if not self.offline_mode:
                # Initial fetch
                initial_flags = self._fetch_flags()
                with self._lock:
                    self.flags = initial_flags

                # Start background threads
                self._polling_thread = threading.Thread(
                    target=self._polling_worker,
                    daemon=True,
                    name="FlagPolling"
                )
                self._polling_thread.start()

                if self.enable_metrics:
                    self._log_upload_thread = threading.Thread(
                        target=self._log_upload_worker,
                        daemon=True,
                        name="LogUpload"
                    )
                    self._log_upload_thread.start()

            if ENABLE_LOGGING: logger.info("SDK initialized successfully")
        except Exception as e:
            if ENABLE_LOGGING: logger.warning(f"SDK initialization failed: {e}, continuing in degraded mode")
        finally:
            self._initialization_complete.set()

    # Public methods

    def get(self, user_id: str, flag_name: str, default_value: Any = None,
            segments: Optional[Dict[str, Any]] = None) -> Any:
        """Get flag value for user with enhanced validation and offline support"""
        # Wait for initialization if still in progress
        if not self._initialization_complete.wait(timeout=5):
            if ENABLE_LOGGING: logger.warning("Initialization still in progress, proceeding anyway")

        # Validate inputs
        try:
            user_id = self._validate_user_id(user_id)
            flag_name = self._validate_flag_name(flag_name)
        except ValueError as e:
            if ENABLE_LOGGING: logger.error(f"Input validation failed: {e}")
            return default_value

        # Sanitize segments
        if segments:
            clean_segments = {}
            for key, value in segments.items():
                if isinstance(key, str) and len(key) <= 128:
                    try:
                        clean_key = self._validate_string(key, "segment_key", 128)
                        clean_segments[clean_key] = value
                    except ValueError:
                        continue
            segments = clean_segments

        # Rate limiting (skip in offline mode)
        if not self.offline_mode and not self._rate_limit_check(user_id):
            if ENABLE_LOGGING: logger.warning(f"Request blocked due to rate limiting: {user_id}")
            return default_value

        with self._lock:
            flag_data = self.flags.get(flag_name)

        if not flag_data:
            # Flag not found, return default
            result = default_value
            evaluation_context = {
                'flag_found': False,
                'default_value_used': True,
                'reason': 'flag_not_found'
            }
            evaluation_time_ms = 0
        else:
            # Evaluate flag
            result, evaluation_context = self._evaluate_flag(flag_data, user_id, segments)
            evaluation_time_ms = evaluation_context.get('total_sdk_time_ms', 0)

            # Use custom default if evaluation returned default and custom default provided
            if evaluation_context.get('default_value_used') and default_value is not None:
                result = default_value

        # Log the access
        self._log_access(user_id, flag_name, result, evaluation_context, evaluation_time_ms, segments)

        return result

    def get_bool(self, user_id: str, flag_name: str, default_value: bool = False,
                 segments: Optional[Dict[str, Any]] = None) -> bool:
        """Get boolean flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value) if value is not None else default_value

    def get_string(self, user_id: str, flag_name: str, default_value: str = "",
                   segments: Optional[Dict[str, Any]] = None) -> str:
        """Get string flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        return str(value) if value is not None else default_value

    def get_int(self, user_id: str, flag_name: str, default_value: int = 0,
                segments: Optional[Dict[str, Any]] = None) -> int:
        """Get integer flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        try:
            return int(float(value)) if value is not None else default_value
        except (ValueError, TypeError):
            return default_value

    def get_float(self, user_id: str, flag_name: str, default_value: float = 0.0,
                  segments: Optional[Dict[str, Any]] = None) -> float:
        """Get float flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        try:
            return float(value) if value is not None else default_value
        except (ValueError, TypeError):
            return default_value

    def get_json(self, user_id: str, flag_name: str, default_value: Any = None,
                 segments: Optional[Dict[str, Any]] = None) -> Any:
        """Get JSON flag value"""
        if default_value is None:
            default_value = {}

        value = self.get(user_id, flag_name, default_value, segments)

        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default_value

        return default_value

    def is_flag_enabled_for_user(self, user_id: str, flag_name: str, segments: Optional[Dict[str, Any]] = None) -> bool:
        """Check if a feature flag is enabled for a specific user"""
        return self.get_bool(user_id, flag_name, False, segments)

    def get_user_flags(self, user_id: str, segments: Optional[Dict[str, Any]] = None,
                       flag_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get multiple feature flags evaluated for a specific user"""
        try:
            user_id = self._validate_user_id(user_id)
        except ValueError as e:
            if ENABLE_LOGGING: logger.error(f"Invalid user_id: {e}")
            return {}

        user_flags = {}

        try:
            with self._lock:
                flags_to_evaluate = self.flags
                if flag_keys:
                    validated_keys = []
                    for key in flag_keys:
                        try:
                            validated_keys.append(self._validate_flag_name(key))
                        except ValueError:
                            continue
                    flags_to_evaluate = {k: v for k, v in self.flags.items() if k in validated_keys}
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Error accessing flags for user flags: {e}")
            return {}

        for flag_key, flag_data in flags_to_evaluate.items():
            try:
                flag_value, evaluation_context = self._evaluate_flag(flag_data, user_id, segments)
                user_flags[flag_key] = flag_value

                # Log each flag access
                evaluation_time_ms = evaluation_context.get('total_sdk_time_ms', 0)
                self._log_access(user_id, flag_key, flag_value, evaluation_context, evaluation_time_ms, segments)
            except Exception as e:
                if ENABLE_LOGGING: logger.error(f"Error evaluating flag {flag_key} for user {user_id}: {e}")
                # Set default based on flag type
                flag_type = flag_data.get('type', 'string')
                user_flags[flag_key] = self._get_default_value(flag_type)

        return user_flags

    def get_all_flags(self) -> Dict[str, Dict]:
        """Get all cached flags"""
        with self._lock:
            return {name: dict(data) for name, data in self.flags.items()}

    def refresh_flags(self) -> bool:
        """Manually refresh flags from server"""
        if self.offline_mode:
            if ENABLE_LOGGING: logger.warning("Cannot refresh flags in offline mode")
            return False

        try:
            new_flags = self._fetch_flags()
            if new_flags:
                with self._lock:
                    self.flags.update(new_flags)
                self.stats['last_sync'] = datetime.now(timezone.utc).isoformat()
                if ENABLE_LOGGING: logger.info("Flags manually refreshed")
                return True
            return False
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Manual refresh failed: {e}")
            return False

    def flush_logs(self) -> bool:
        """Manually flush logs to server"""
        if self.offline_mode or not self.enable_metrics:
            if ENABLE_LOGGING: logger.warning("Cannot flush logs in offline mode or with metrics disabled")
            return False

        try:
            self._upload_logs()
            if ENABLE_LOGGING: logger.info("Logs manually flushed")
            return True
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Manual log flush failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get comprehensive SDK usage statistics"""
        try:
            with self._stats_lock:
                eval_times = self.stats['evaluation_times']
                avg_ms = (eval_times['total_ms'] / eval_times['count']) if eval_times['count'] > 0 else 0

                return {
                    'total_user_accesses': self.stats['total_user_accesses'],
                    'unique_users_count': len(self.stats['unique_users']),
                    'unique_flags_count': len(self.stats['unique_flags_accessed']),
                    'segment_matches': self.stats['segment_matches'],
                    'rollout_evaluations': self.stats['rollout_evaluations'],
                    'last_sync': self.stats['last_sync'],
                    'last_log_upload': self.stats['last_log_upload'],
                    'api_calls': self.stats['api_calls'].copy(),
                    'errors': self.stats['errors'].copy(),
                    'session_id': self.session_id,
                    'cached_flags_count': len(self.flags),
                    'pending_user_logs': self.logs_queue.qsize(),
                    'circuit_breaker': {
                        'state': self._circuit_breaker['state'],
                        'failure_count': self._circuit_breaker['failure_count']
                    },
                    'evaluation_times': {
                        'avg_ms': avg_ms,
                        'min_ms': eval_times['min_ms'] if eval_times['min_ms'] != float('inf') else 0,
                        'max_ms': eval_times['max_ms'],
                        'total_ms': eval_times['total_ms'],
                        'count': eval_times['count']
                    },
                    'configuration': {
                        'polling_interval': POLLING_INTERVAL,
                        'log_upload_interval': LOG_UPLOAD_INTERVAL,
                        'offline_mode': self.offline_mode,
                        'enable_metrics': self.enable_metrics,
                        'environment': self.environment
                    }
                }
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Error getting stats: {e}")
            return {'error': str(e)}

    def get_health_check(self) -> Dict[str, Any]:
        """Get comprehensive SDK health status"""
        try:
            with self._lock:
                cached_flags_count = len(self.flags)

            return {
                'status': 'healthy' if self._circuit_breaker['state'] != 'open' else 'degraded',
                'sdk_version': SDK_VERSION,
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
                'system_info': self._system_info,
                'initialization_complete': self._initialization_complete.is_set()
            }
        except Exception as e:
            if ENABLE_LOGGING: logger.error(f"Error getting health check: {e}")
            return {'status': 'error', 'error': str(e)}

    def shutdown(self):
        """Shutdown SDK"""
        if ENABLE_LOGGING: logger.info("Shutting down SDK...")

        # Stop background threads
        self._stop_event.set()

        # Upload remaining logs
        if self.enable_metrics and not self.offline_mode:
            try:
                self._upload_logs()
            except Exception as e:
                if ENABLE_LOGGING: logger.warning(f"Error during final log upload: {e}")

        # Wait for threads to finish with better cleanup
        threads_to_join = [self._polling_thread, self._log_upload_thread]
        for thread in threads_to_join:
            if thread and thread.is_alive():
                try:
                    thread.join(timeout=5)  # Increased timeout
                    if thread.is_alive():
                        if ENABLE_LOGGING: logger.warning(f"Thread {thread.name} did not terminate within timeout")
                except Exception as e:
                    if ENABLE_LOGGING: logger.warning(f"Error joining thread {thread.name}: {e}")

        # Close session
        try:
            if hasattr(self, 'session') and self.session:
                self.session.close()
        except Exception as e:
            if ENABLE_LOGGING: logger.warning(f"Error closing session: {e}")

        # Clear references to prevent memory leaks
        self._polling_thread = None
        self._log_upload_thread = None

        if ENABLE_LOGGING: logger.info("SDK shutdown complete")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


# Utility functions for production deployment

def validate_production_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration for production deployment"""
    warnings = []

    if config.get('api_base_url', '').startswith('http://'):
        warnings.append("Using HTTP instead of HTTPS - security risk")

    if config.get('timeout', 30) < 5:
        warnings.append("Timeout too low - may cause instability")

    if not config.get('client_secret', ''):
        warnings.append("Missing client secret")

    client_secret = config.get('client_secret', '')
    if len(client_secret) < 32:
        warnings.append("Client secret appears to be weak")

    return warnings


def create_production_client(client_id: str, client_secret: str, environment: str, **kwargs) -> FeatureFlagsHQSDK:
    """Create a production-ready SDK instance with security hardening"""

    secure_config = {
        'timeout': 30,
        'max_retries': 3,
        'offline_mode': False,
        'enable_metrics': True,
        **kwargs
    }

    # Validate configuration
    warnings = validate_production_config(secure_config)
    if warnings:
        for warning in warnings:
            if ENABLE_LOGGING: logger.warning(f"Configuration warning: {warning}")

    # Create SDK instance
    sdk = FeatureFlagsHQSDK(
        client_id=client_id,
        client_secret=client_secret,
        environment=environment,
        **secure_config
    )

    if ENABLE_LOGGING: logger.info(f"Secure {COMPANY_NAME} SDK initialized with production configuration")
    return sdk
