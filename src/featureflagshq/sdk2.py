"""
Simplified FeatureFlagsHQ SDK - Clean and focused implementation
Core functionality without over-engineering
"""

import json
import time
import threading
import hashlib
import hmac
import base64
import uuid
import platform
import os
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
from queue import Queue, Empty
import requests
import logging

# Constants
MAX_USER_ID_LENGTH = 255
MAX_FLAG_NAME_LENGTH = 255
POLLING_INTERVAL = 300  # 5 minutes
LOG_UPLOAD_INTERVAL = 120  # 2 minutes

# Setup logging
logger = logging.getLogger('featureflagshq_sdk2')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FeatureFlagSDK:
    """Simplified Feature Flag SDK"""
    
    def __init__(self, client_id: str = None, client_secret: str = None, api_base_url: str = "https://api.featureflagshq.com", environment: str = None):
        # Get credentials from environment if not provided
        if not client_id:
            client_id = os.getenv('FEATUREFLAGSHQ_CLIENT_ID')
        if not client_secret:
            client_secret = os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET')
        if not environment:
            environment = os.getenv('FEATUREFLAGSHQ_ENVIRONMENT', 'production')
            
        # Validate inputs
        if not client_id or not client_secret:
            raise ValueError("client_id and client_secret are required (provide directly or via FEATUREFLAGSHQ_CLIENT_ID and FEATUREFLAGSHQ_CLIENT_SECRET environment variables)")
        
        self.client_id = self._validate_string(client_id, "client_id")
        self.client_secret = self._validate_string(client_secret, "client_secret")
        self.api_base_url = api_base_url.rstrip('/')
        self.environment = self._validate_string(environment, "environment")
        
        # Internal state
        self.flags = {}  # flag_name -> flag_data
        self.session_id = str(uuid.uuid4())
        self.logs_queue = Queue()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        
        # Background threads
        self._polling_thread = None
        self._log_upload_thread = None
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.timeout = 10
        
        # Start SDK
        self._initialize()
    
    def _validate_string(self, value: str, field_name: str, max_length: int = 255) -> str:
        """Validate and sanitize string inputs"""
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        
        # Remove dangerous characters
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} cannot be empty")
        
        # Check length
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
        """Validate user ID"""
        return self._validate_string(user_id, "user_id", MAX_USER_ID_LENGTH)
    
    def _validate_flag_name(self, flag_name: str) -> str:
        """Validate flag name"""
        return self._validate_string(flag_name, "flag_name", MAX_FLAG_NAME_LENGTH)
    
    def _generate_signature(self, payload: str, timestamp: str) -> str:
        """Generate HMAC signature for API authentication"""
        message = f"{self.client_id}:{timestamp}:{payload}"
        signature = hmac.new(
            self.client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        return signature_b64
    
    def _get_headers(self, payload: str = "") -> Dict[str, str]:
        """Get headers for API requests"""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(payload, timestamp)
        
        return {
            'Content-Type': 'application/json',
            'X-SDK-Provider': 'FeatureFlagsHQ',
            'X-Client-ID': self.client_id,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
            'X-Session-ID': self.session_id,
            'X-SDK-Version': '2.0.0',
            'X-Environment': self.environment,
            'User-Agent': 'FeatureFlagsHQ-Python-SDK/2.0.0'
        }
    
    def _fetch_flags(self) -> Dict[str, Any]:
        """Fetch flags from server"""
        try:
            url = f"{self.api_base_url}/v1/flags/"
            headers = self._get_headers("")
            
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            flags = {}
            
            if 'data' in data and isinstance(data['data'], list):
                for flag_data in data['data']:
                    if isinstance(flag_data, dict) and 'name' in flag_data:
                        flag_name = flag_data['name']
                        if isinstance(flag_name, str) and flag_name:
                            flags[flag_name] = flag_data
            
            logger.info(f"Fetched {len(flags)} flags from server")
            return flags
            
        except Exception as e:
            logger.error(f"Failed to fetch flags: {e}")
            return {}
    
    def _evaluate_flag(self, flag_data: Dict[str, Any], user_id: str, segments: Optional[Dict[str, Any]] = None) -> Any:
        """Evaluate flag for user"""
        if not flag_data.get('is_active', True):
            return self._get_default_value(flag_data.get('type', 'string'))
        
        # Check segments if provided
        if segments and flag_data.get('segments'):
            segment_match = self._check_segments(flag_data['segments'], segments)
            if not segment_match:
                return self._get_default_value(flag_data.get('type', 'string'))
        
        # Check rollout percentage
        rollout_percentage = flag_data.get('rollout', {}).get('percentage', 100)
        if rollout_percentage < 100:
            user_hash = hashlib.sha256(f"{flag_data['name']}:{user_id}".encode()).hexdigest()
            user_percentage = int(user_hash[:8], 16) % 100
            if user_percentage >= rollout_percentage:
                return self._get_default_value(flag_data.get('type', 'string'))
        
        # Return flag value
        return self._convert_value(flag_data.get('value'), flag_data.get('type', 'string'))
    
    def _check_segments(self, flag_segments: List[Dict], user_segments: Dict[str, Any]) -> bool:
        """Check if user matches any segment"""
        for segment in flag_segments:
            if not isinstance(segment, dict):
                continue
            
            segment_name = segment.get('name')
            if segment_name in user_segments:
                if self._evaluate_segment(segment, user_segments[segment_name]):
                    return True
        return False
    
    def _evaluate_segment(self, segment: Dict, user_value: Any) -> bool:
        """Evaluate single segment condition"""
        try:
            comparator = segment.get('comparator', '==')
            segment_value = segment.get('value')
            segment_type = segment.get('type', 'string')
            
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
    
    def _log_access(self, user_id: str, flag_name: str, flag_value: Any, segments: Optional[Dict] = None):
        """Log flag access for analytics"""
        log_entry = {
            'user_id': user_id,
            'flag_name': flag_name,
            'flag_value': flag_value,
            'segments': segments or {},
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'session_id': self.session_id,
            'system_info': {
                'platform': platform.system(),
                'python_version': platform.python_version(),
                'hostname': platform.node(),
                'process_id': os.getpid()
            }
        }
        
        try:
            self.logs_queue.put(log_entry, block=False)
        except:
            # Queue is full, ignore
            pass
    
    def _upload_logs(self):
        """Upload logs to server"""
        if self.logs_queue.empty():
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
            payload = {'logs': logs}
            payload_str = json.dumps(payload)
            headers = self._get_headers(payload_str)
            
            response = self.session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            logger.debug(f"Uploaded {len(logs)} log entries")
            
        except Exception as e:
            logger.error(f"Failed to upload logs: {e}")
            # Put logs back in queue for retry
            for log in logs:
                try:
                    self.logs_queue.put(log, block=False)
                except:
                    break
    
    def _polling_worker(self):
        """Background worker to poll for flag updates"""
        while not self._stop_event.wait(POLLING_INTERVAL):
            try:
                new_flags = self._fetch_flags()
                if new_flags:
                    with self._lock:
                        self.flags.update(new_flags)
                    logger.debug("Updated flags from polling")
            except Exception as e:
                logger.error(f"Error in polling worker: {e}")
    
    def _log_upload_worker(self):
        """Background worker to upload logs"""
        while not self._stop_event.wait(LOG_UPLOAD_INTERVAL):
            try:
                self._upload_logs()
            except Exception as e:
                logger.error(f"Error in log upload worker: {e}")
    
    def _initialize(self):
        """Initialize SDK"""
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
        
        self._log_upload_thread = threading.Thread(
            target=self._log_upload_worker,
            daemon=True,
            name="LogUpload"
        )
        self._log_upload_thread.start()
        
        logger.info("SDK initialized successfully")
    
    # Public methods
    
    def get(self, user_id: str, flag_name: str, default_value: Any = None, segments: Optional[Dict[str, Any]] = None) -> Any:
        """Get flag value for user"""
        # Validate inputs
        user_id = self._validate_user_id(user_id)
        flag_name = self._validate_flag_name(flag_name)
        
        # Sanitize segments
        if segments:
            clean_segments = {}
            for key, value in segments.items():
                if isinstance(key, str) and len(key) <= 128:
                    clean_key = self._validate_string(key, "segment_key", 128)
                    clean_segments[clean_key] = value
            segments = clean_segments
        
        with self._lock:
            flag_data = self.flags.get(flag_name)
        
        if not flag_data:
            # Flag not found, return default
            result = default_value
        else:
            # Evaluate flag
            result = self._evaluate_flag(flag_data, user_id, segments)
            
            # Use custom default if evaluation returned default and custom default provided
            if result == self._get_default_value(flag_data.get('type', 'string')) and default_value is not None:
                result = default_value
        
        # Log the access
        self._log_access(user_id, flag_name, result, segments)
        
        return result
    
    def get_bool(self, user_id: str, flag_name: str, default_value: bool = False, segments: Optional[Dict[str, Any]] = None) -> bool:
        """Get boolean flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value) if value is not None else default_value
    
    def get_string(self, user_id: str, flag_name: str, default_value: str = "", segments: Optional[Dict[str, Any]] = None) -> str:
        """Get string flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        return str(value) if value is not None else default_value
    
    def get_int(self, user_id: str, flag_name: str, default_value: int = 0, segments: Optional[Dict[str, Any]] = None) -> int:
        """Get integer flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        try:
            return int(float(value)) if value is not None else default_value
        except (ValueError, TypeError):
            return default_value
    
    def get_float(self, user_id: str, flag_name: str, default_value: float = 0.0, segments: Optional[Dict[str, Any]] = None) -> float:
        """Get float flag value"""
        value = self.get(user_id, flag_name, default_value, segments)
        try:
            return float(value) if value is not None else default_value
        except (ValueError, TypeError):
            return default_value
    
    def get_json(self, user_id: str, flag_name: str, default_value: Any = None, segments: Optional[Dict[str, Any]] = None) -> Any:
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
    
    def get_all_flags(self) -> Dict[str, Dict]:
        """Get all cached flags"""
        with self._lock:
            return {name: dict(data) for name, data in self.flags.items()}
    
    def refresh_flags(self) -> bool:
        """Manually refresh flags from server"""
        try:
            new_flags = self._fetch_flags()
            if new_flags:
                with self._lock:
                    self.flags.update(new_flags)
                return True
            return False
        except Exception as e:
            logger.error(f"Manual refresh failed: {e}")
            return False
    
    def flush_logs(self) -> bool:
        """Manually flush logs to server"""
        try:
            self._upload_logs()
            return True
        except Exception as e:
            logger.error(f"Manual log flush failed: {e}")
            return False
    
    def shutdown(self):
        """Shutdown SDK"""
        logger.info("Shutting down SDK...")
        
        # Stop background threads
        self._stop_event.set()
        
        # Upload remaining logs
        try:
            self._upload_logs()
        except Exception as e:
            logger.warning(f"Error during final log upload: {e}")
        
        # Wait for threads to finish
        for thread in [self._polling_thread, self._log_upload_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=2)
        
        # Close session
        try:
            self.session.close()
        except Exception as e:
            logger.warning(f"Error closing session: {e}")
        
        logger.info("SDK shutdown complete")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()