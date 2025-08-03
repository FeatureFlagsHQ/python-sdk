# FeatureFlagsHQ Python SDK

[![PyPI version](https://badge.fury.io/py/featureflagshq-sdk.svg)](https://badge.fury.io/py/featureflagshq-sdk)
[![Python Support](https://img.shields.io/pypi/pyversions/featureflagshq-sdk.svg)](https://pypi.org/project/featureflagshq-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A secure, high-performance Python SDK for [FeatureFlagsHQ](https://featureflagshq.com) feature flag management with enterprise-grade security, offline support, and comprehensive analytics.

## Features

- 🔒 **Enterprise Security**: HMAC authentication, input validation, and security filtering
- ⚡ **High Performance**: Background polling, caching, and circuit breaker patterns
- 🌐 **Offline Support**: Works seamlessly without internet connectivity
- 📊 **Analytics & Metrics**: Comprehensive usage tracking and statistics
- 🎯 **User Segmentation**: Advanced targeting based on user attributes
- 🔄 **Real-time Updates**: Background flag synchronization with change callbacks
- 🛡️ **Production Ready**: Rate limiting, error handling, and graceful degradation

## Installation

```bash
pip install featureflagshq-sdk
```

## Quick Start

```python
from featureflagshq import FeatureFlagsHQSDK

# Initialize the SDK
sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret",
    environment="production"  # or "staging", "development"
)

# Get a feature flag value
user_id = "user_123"
is_enabled = sdk.get_bool(user_id, "new_dashboard", default_value=False)

if is_enabled:
    print("New dashboard is enabled for this user!")
else:
    print("Using classic dashboard")

# Clean shutdown
sdk.shutdown()
```

## Configuration

### Environment Variables

The SDK can be configured using environment variables:

```bash
export FEATUREFLAGSHQ_CLIENT_ID="your_client_id"
export FEATUREFLAGSHQ_CLIENT_SECRET="your_client_secret"
export FEATUREFLAGSHQ_ENVIRONMENT="production"
```

```python
# SDK will automatically use environment variables
sdk = FeatureFlagsHQSDK()
```

### Advanced Configuration

```python
sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret",
    environment="production",
    api_base_url="https://api.featureflagshq.com",  # Custom API endpoint
    timeout=30,                                      # Request timeout
    max_retries=3,                                   # Number of retries
    offline_mode=False,                              # Enable offline mode
    enable_metrics=True,                             # Enable analytics
    on_flag_change=lambda name, old, new: print(f"Flag {name} changed!")
)
```

## Usage Examples

### Basic Flag Evaluation

```python
from featureflagshq import FeatureFlagsHQSDK

sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret"
)

user_id = "user_123"

# Boolean flags
show_beta_feature = sdk.get_bool(user_id, "beta_feature", default_value=False)

# String flags
button_color = sdk.get_string(user_id, "button_color", default_value="blue")

# Integer flags
max_items = sdk.get_int(user_id, "max_items_per_page", default_value=10)

# Float flags
discount_rate = sdk.get_float(user_id, "discount_rate", default_value=0.0)

# JSON flags
config = sdk.get_json(user_id, "app_config", default_value={})
```

### User Segmentation

```python
# Define user segments for targeting
user_segments = {
    "country": "US",
    "subscription": "premium",
    "age": 25,
    "beta_user": True
}

# Evaluate flags with segments
is_premium_feature_enabled = sdk.get_bool(
    user_id="user_123",
    flag_name="premium_analytics",
    default_value=False,
    segments=user_segments
)
```

### Bulk Flag Evaluation

```python
# Get all flags for a user
all_flags = sdk.get_user_flags("user_123", segments=user_segments)
print(f"All flags for user: {all_flags}")

# Get specific flags only
specific_flags = sdk.get_user_flags(
    "user_123", 
    segments=user_segments,
    flag_keys=["feature_a", "feature_b", "feature_c"]
)
```

### Context Manager Usage

```python
# Automatic cleanup with context manager
with FeatureFlagsHQSDK(client_id="...", client_secret="...") as sdk:
    is_enabled = sdk.get_bool("user_123", "new_feature")
    # SDK automatically shuts down when exiting the context
```

### Production Setup

```python
from featureflagshq import create_production_client

# Create a production-ready client with security hardening
sdk = create_production_client(
    client_id="your_client_id",
    client_secret="your_client_secret",
    environment="production",
    timeout=30,
    max_retries=3
)
```

### Flask Integration

```python
from flask import Flask, request
from featureflagshq import FeatureFlagsHQSDK

app = Flask(__name__)

# Initialize SDK once
sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret"
)

@app.route('/dashboard')
def dashboard():
    user_id = request.user.id  # Get from your auth system
    
    # Check if new dashboard is enabled
    use_new_dashboard = sdk.get_bool(user_id, "new_dashboard_v2")
    
    if use_new_dashboard:
        return render_template('dashboard_v2.html')
    else:
        return render_template('dashboard_v1.html')

# Clean shutdown when app closes
@app.teardown_appcontext
def shutdown_sdk(exception):
    sdk.shutdown()
```

### Django Integration

```python
# settings.py
FEATUREFLAGSHQ_CLIENT_ID = "your_client_id"
FEATUREFLAGSHQ_CLIENT_SECRET = "your_client_secret"
FEATUREFLAGSHQ_ENVIRONMENT = "production"

# utils.py
from django.conf import settings
from featureflagshq import FeatureFlagsHQSDK

_sdk_instance = None

def get_feature_flags_sdk():
    global _sdk_instance
    if _sdk_instance is None:
        _sdk_instance = FeatureFlagsHQSDK(
            client_id=settings.FEATUREFLAGSHQ_CLIENT_ID,
            client_secret=settings.FEATUREFLAGSHQ_CLIENT_SECRET,
            environment=settings.FEATUREFLAGSHQ_ENVIRONMENT
        )
    return _sdk_instance

# views.py
from django.shortcuts import render
from .utils import get_feature_flags_sdk

def my_view(request):
    sdk = get_feature_flags_sdk()
    user_id = str(request.user.id)
    
    show_new_feature = sdk.get_bool(user_id, "new_feature")
    
    return render(request, 'template.html', {
        'show_new_feature': show_new_feature
    })
```

## Advanced Features

### Flag Change Callbacks

```python
def on_flag_changed(flag_name, old_value, new_value):
    print(f"Flag '{flag_name}' changed from {old_value} to {new_value}")
    # Trigger cache invalidation, send notifications, etc.

sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret",
    on_flag_change=on_flag_changed
)
```

### Manual Refresh and Cache Control

```python
# Manually refresh flags from server
success = sdk.refresh_flags()
if success:
    print("Flags refreshed successfully")

# Get all cached flags
all_flags = sdk.get_all_flags()
print(f"Cached flags: {list(all_flags.keys())}")

# Force log upload
sdk.flush_logs()
```

### SDK Health and Statistics

```python
# Get SDK health status
health = sdk.get_health_check()
print(f"SDK Status: {health['status']}")
print(f"Cached Flags: {health['cached_flags_count']}")

# Get detailed usage statistics
stats = sdk.get_stats()
print(f"Total API calls: {stats['api_calls']['total']}")
print(f"Unique users: {stats['unique_users_count']}")
print(f"Circuit breaker state: {stats['circuit_breaker']['state']}")
```

### Offline Mode

```python
# Enable offline mode for environments without internet
sdk = FeatureFlagsHQSDK(
    client_id="your_client_id",
    client_secret="your_client_secret",
    offline_mode=True
)

# All flag evaluations will use default values in offline mode
result = sdk.get_bool("user_123", "feature_flag", default_value=True)
```

## Error Handling

The SDK includes comprehensive error handling and graceful degradation:

```python
try:
    sdk = FeatureFlagsHQSDK(
        client_id="invalid_client_id",
        client_secret="invalid_secret"
    )
    
    # SDK will continue to work but use default values
    # Check health to see if there are authentication issues
    health = sdk.get_health_check()
    if health['status'] != 'healthy':
        print(f"SDK not healthy: {health}")
        
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Best Practices

### 1. Singleton Pattern
Create one SDK instance per application and reuse it:

```python
# Good
sdk = FeatureFlagsHQSDK(client_id="...", client_secret="...")
# Reuse sdk throughout your application

# Bad - creates multiple instances
def get_flag():
    sdk = FeatureFlagsHQSDK(client_id="...", client_secret="...")
    return sdk.get_bool("user", "flag")
```

### 2. Always Provide Default Values
```python
# Good - provides fallback behavior
is_enabled = sdk.get_bool("user_123", "new_feature", default_value=False)

# Risky - might return None in error cases
is_enabled = sdk.get_bool("user_123", "new_feature")
```

### 3. Use Context Managers for Short-lived Usage
```python
# For scripts or short-lived processes
with FeatureFlagsHQSDK(client_id="...", client_secret="...") as sdk:
    result = sdk.get_bool("user", "flag")
    # Automatic cleanup
```

### 4. Monitor SDK Health
```python
# Periodically check SDK health in production
health = sdk.get_health_check()
if health['status'] != 'healthy':
    # Alert your monitoring system
    logger.warning(f"FeatureFlags SDK unhealthy: {health}")
```

## API Reference

### Main Methods

- `get(user_id, flag_name, default_value, segments)` - Get flag value with type inference
- `get_bool(user_id, flag_name, default_value, segments)` - Get boolean flag
- `get_string(user_id, flag_name, default_value, segments)` - Get string flag
- `get_int(user_id, flag_name, default_value, segments)` - Get integer flag
- `get_float(user_id, flag_name, default_value, segments)` - Get float flag
- `get_json(user_id, flag_name, default_value, segments)` - Get JSON flag
- `get_user_flags(user_id, segments, flag_keys)` - Get multiple flags for user
- `is_flag_enabled_for_user(user_id, flag_name, segments)` - Check if flag is enabled

### Management Methods

- `refresh_flags()` - Manually refresh flags from server
- `flush_logs()` - Upload pending analytics logs
- `get_all_flags()` - Get all cached flag definitions
- `get_stats()` - Get SDK usage statistics
- `get_health_check()` - Get SDK health status
- `shutdown()` - Clean shutdown of background threads

## Security

The SDK implements multiple security layers:

- **HMAC Authentication**: All API requests are signed with HMAC-SHA256
- **Input Validation**: All inputs are validated and sanitized
- **Security Filtering**: Sensitive data is filtered from logs
- **Rate Limiting**: Per-user rate limiting prevents abuse
- **Circuit Breaker**: Automatic failure detection and recovery

## Support

- **Documentation**: [https://docs.featureflagshq.com](https://docs.featureflagshq.com)
- **Issues**: [GitHub Issues](https://github.com/featureflagshq/python-sdk/issues)
- **Email**: hello@featureflagshq.com

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.