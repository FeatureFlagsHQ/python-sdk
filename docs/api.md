# FeatureFlagsHQ SDK API Reference

## Table of Contents

- [SDK Initialization](#sdk-initialization)
- [Core Methods](#core-methods)
- [Type-Specific Methods](#type-specific-methods)
- [Bulk Operations](#bulk-operations)
- [Management Methods](#management-methods)
- [Monitoring Methods](#monitoring-methods)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Advanced Features](#advanced-features)

## SDK Initialization

### FeatureFlagsHQSDK

```python
FeatureFlagsHQSDK(
    client_id: str = None,
    client_secret: str = None,
    api_base_url: str = "https://api.featureflagshq.com",
    environment: str = None,
    timeout: int = 30,
    max_retries: int = 3,
    offline_mode: bool = False,
    enable_metrics: bool = True,
    on_flag_change: Optional[Callable[[str, Any, Any], None]] = None
)
```

**Parameters:**
- `client_id` (str): Your FeatureFlagsHQ client ID
- `client_secret` (str): Your FeatureFlagsHQ client secret
- `api_base_url` (str): API base URL (default: https://api.featureflagshq.com)
- `environment` (str): Environment name (e.g., "production", "staging")
- `timeout` (int): Request timeout in seconds (default: 30)
- `max_retries` (int): Maximum retry attempts (default: 3)
- `offline_mode` (bool): Enable offline mode (default: False)
- `enable_metrics` (bool): Enable analytics collection (default: True)
- `on_flag_change` (callable): Callback for flag changes

**Example:**
```python
from featureflagshq import FeatureFlagsHQSDK

sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret",
    environment="production"
)
```

### create_production_client

```python
create_production_client(
    client_id: str,
    client_secret: str,
    environment: str,
    **kwargs
) -> FeatureFlagsHQSDK
```

Creates a production-ready SDK instance with security hardening.

**Example:**
```python
from featureflagshq import create_production_client

sdk = create_production_client(
    client_id="your_client_id",
    client_secret="your_client_secret",
    environment="production"
)
```

## Core Methods

### get

```python
get(
    user_id: str,
    flag_name: str,
    default_value: Any = None,
    segments: Optional[Dict[str, Any]] = None
) -> Any
```

Get a feature flag value with automatic type inference.

**Parameters:**
- `user_id` (str): Unique user identifier
- `flag_name` (str): Name of the feature flag
- `default_value` (Any): Default value if flag not found
- `segments` (dict): User segments for targeting

**Returns:** Flag value with original type

**Example:**
```python
value = sdk.get("user_123", "button_color", default_value="blue")
```

## Type-Specific Methods

### get_bool

```python
get_bool(
    user_id: str,
    flag_name: str,
    default_value: bool = False,
    segments: Optional[Dict[str, Any]] = None
) -> bool
```

Get a boolean feature flag value.

**Example:**
```python
is_enabled = sdk.get_bool("user_123", "new_feature", default_value=False)
```

### get_string

```python
get_string(
    user_id: str,
    flag_name: str,
    default_value: str = "",
    segments: Optional[Dict[str, Any]] = None
) -> str
```

Get a string feature flag value.

**Example:**
```python
theme = sdk.get_string("user_123", "theme_color", default_value="blue")
```

### get_int

```python
get_int(
    user_id: str,
    flag_name: str,
    default_value: int = 0,
    segments: Optional[Dict[str, Any]] = None
) -> int
```

Get an integer feature flag value.

**Example:**
```python
max_items = sdk.get_int("user_123", "max_items", default_value=10)
```

### get_float

```python
get_float(
    user_id: str,
    flag_name: str,
    default_value: float = 0.0,
    segments: Optional[Dict[str, Any]] = None
) -> float
```

Get a float feature flag value.

**Example:**
```python
rate = sdk.get_float("user_123", "discount_rate", default_value=0.1)
```

### get_json

```python
get_json(
    user_id: str,
    flag_name: str,
    default_value: Any = None,
    segments: Optional[Dict[str, Any]] = None
) -> Any
```

Get a JSON feature flag value (dict or list).

**Example:**
```python
config = sdk.get_json("user_123", "app_config", default_value={})
```

## Bulk Operations

### get_user_flags

```python
get_user_flags(
    user_id: str,
    segments: Optional[Dict[str, Any]] = None,
    flag_keys: Optional[List[str]] = None
) -> Dict[str, Any]
```

Get multiple feature flags for a user.

**Parameters:**
- `user_id` (str): Unique user identifier
- `segments` (dict): User segments for targeting
- `flag_keys` (list): Specific flag names to retrieve (optional)

**Returns:** Dictionary of flag names to values

**Example:**
```python
# Get all flags
all_flags = sdk.get_user_flags("user_123")

# Get specific flags
specific_flags = sdk.get_user_flags(
    "user_123", 
    flag_keys=["feature_a", "feature_b"]
)
```

### is_flag_enabled_for_user

```python
is_flag_enabled_for_user(
    user_id: str,
    flag_name: str,
    segments: Optional[Dict[str, Any]] = None
) -> bool
```

Convenience method to check if a flag is enabled.

**Example:**
```python
enabled = sdk.is_flag_enabled_for_user("user_123", "beta_features")
```

## Management Methods

### refresh_flags

```python
refresh_flags() -> bool
```

Manually refresh flags from the server.

**Returns:** True if successful, False otherwise

**Example:**
```python
success = sdk.refresh_flags()
if success:
    print("Flags refreshed successfully")
```

### flush_logs

```python
flush_logs() -> bool
```

Manually upload pending analytics logs.

**Returns:** True if successful, False otherwise

**Example:**
```python
success = sdk.flush_logs()
```

### get_all_flags

```python
get_all_flags() -> Dict[str, Dict]
```

Get all cached flag definitions.

**Returns:** Dictionary of flag names to flag data

**Example:**
```python
all_flags = sdk.get_all_flags()
for flag_name, flag_data in all_flags.items():
    print(f"Flag: {flag_name}, Active: {flag_data.get('is_active')}")
```

### shutdown

```python
shutdown() -> None
```

Clean shutdown of background threads and resources.

**Example:**
```python
sdk.shutdown()
```

## Monitoring Methods

### get_stats

```python
get_stats() -> Dict
```

Get comprehensive SDK usage statistics.

**Returns:** Dictionary with statistics

**Example:**
```python
stats = sdk.get_stats()
print(f"Total accesses: {stats['total_user_accesses']}")
print(f"Unique users: {stats['unique_users_count']}")
print(f"API calls: {stats['api_calls']['total']}")
```

**Statistics Include:**
- `total_user_accesses`: Total number of flag evaluations
- `unique_users_count`: Number of unique users
- `unique_flags_count`: Number of unique flags accessed
- `last_sync`: Last successful flag synchronization
- `last_log_upload`: Last log upload timestamp
- `api_calls`: API call statistics (total, successful, failed)
- `errors`: Error counts by type
- `session_id`: Current session identifier
- `cached_flags_count`: Number of cached flags
- `pending_user_logs`: Number of pending log entries
- `circuit_breaker`: Circuit breaker state and failure count

### get_health_check

```python
get_health_check() -> Dict[str, Any]
```

Get comprehensive SDK health status.

**Returns:** Dictionary with health information

**Example:**
```python
health = sdk.get_health_check()
print(f"Status: {health['status']}")
print(f"SDK Version: {health['sdk_version']}")
print(f"Cached Flags: {health['cached_flags_count']}")
```

**Health Check Includes:**
- `status`: Overall health status ("healthy", "degraded", "error")
- `sdk_version`: SDK version
- `api_base_url`: Configured API URL
- `cached_flags_count`: Number of cached flags
- `session_id`: Current session ID
- `environment`: Configured environment
- `offline_mode`: Whether offline mode is enabled
- `last_sync`: Last synchronization timestamp
- `circuit_breaker`: Circuit breaker status
- `system_info`: Platform and Python version info
- `initialization_complete`: Whether initialization finished

## Configuration

### Environment Variables

The SDK supports configuration via environment variables:

- `FEATUREFLAGSHQ_CLIENT_ID`: Client ID
- `FEATUREFLAGSHQ_CLIENT_SECRET`: Client secret  
- `FEATUREFLAGSHQ_ENVIRONMENT`: Environment name

### User Segmentation

User segments allow advanced targeting based on user attributes:

```python
segments = {
    "country": "US",
    "subscription": "premium", 
    "age": 25,
    "beta_user": True,
    "signup_date": "2023-01-15"
}

result = sdk.get_bool("user_123", "premium_feature", segments=segments)
```

**Supported Comparators:**
- `==`: Equal to
- `!=`: Not equal to
- `>`: Greater than
- `<`: Less than
- `>=`: Greater than or equal
- `<=`: Less than or equal
- `contains`: String contains substring

## Error Handling

The SDK implements graceful error handling:

### Circuit Breaker

Automatically opens when failure threshold is reached (default: 5 failures):

```python
# Check circuit breaker state
stats = sdk.get_stats()
print(f"Circuit breaker: {stats['circuit_breaker']['state']}")
```

States:
- `closed`: Normal operation
- `open`: Blocking requests due to failures
- `half-open`: Testing if service has recovered

### Rate Limiting

Per-user rate limiting (default: 1000 requests/minute):

```python
# Rate limiting is automatic and transparent
result = sdk.get_bool("user_123", "flag_name")
```

### Offline Mode

SDK continues working with default values when offline:

```python
sdk = FeatureFlagsHQSDK(
    client_id="client_id",
    client_secret="client_secret", 
    offline_mode=True
)

# Returns default_value when offline
result = sdk.get_bool("user_123", "flag_name", default_value=True)
```

## Advanced Features

### Flag Change Callbacks

Register callbacks for flag changes:

```python
def on_flag_change(flag_name, old_value, new_value):
    print(f"Flag {flag_name} changed: {old_value} -> {new_value}")

sdk = FeatureFlagsHQSDK(
    client_id="client_id",
    client_secret="client_secret",
    on_flag_change=on_flag_change
)
```

### Context Manager

Automatic cleanup with context managers:

```python
with FeatureFlagsHQSDK(client_id="...", client_secret="...") as sdk:
    result = sdk.get_bool("user_123", "flag_name")
    # SDK automatically shuts down
```

### Production Helpers

```python
from featureflagshq import validate_production_config

# Validate configuration
config = {
    'api_base_url': 'https://api.featureflagshq.com',
    'timeout': 30,
    'client_secret': 'your_secret'
}

warnings = validate_production_config(config)
for warning in warnings:
    print(f"Warning: {warning}")
```

### Threading Safety

The SDK is thread-safe and uses locks for concurrent access:

```python
import threading

def worker():
    result = sdk.get_bool("user_123", "flag_name")

# Safe to use from multiple threads
threads = [threading.Thread(target=worker) for _ in range(10)]
for thread in threads:
    thread.start()
```

### Memory Management

Automatic cleanup of old statistics to prevent memory bloat:

- Maximum 10,000 unique users tracked
- Maximum 1,000 unique flags tracked
- Automatic cleanup when limits exceeded

### Security Features

- HMAC-SHA256 signed requests
- Input validation and sanitization
- SQL injection protection
- Sensitive data filtering in logs
- Secure credential handling

### Performance Optimizations

- Background flag polling (5-minute intervals)
- Local caching with thread-safe access
- Connection pooling for HTTP requests
- Efficient statistics tracking
- Minimal memory footprint

## Constants

```python
MAX_USER_ID_LENGTH = 255
MAX_FLAG_NAME_LENGTH = 255
POLLING_INTERVAL = 300  # 5 minutes
LOG_UPLOAD_INTERVAL = 120  # 2 minutes
MAX_UNIQUE_USERS_TRACKED = 10000
MAX_UNIQUE_FLAGS_TRACKED = 1000
```