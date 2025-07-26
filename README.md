# FeatureFlagsHQ Python SDK

[![PyPI version](https://badge.fury.io/py/featureflagshq.svg)](https://badge.fury.io/py/featureflagshq)
[![Python Support](https://img.shields.io/pypi/pyversions/featureflagshq.svg)](https://pypi.org/project/featureflagshq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://github.com/featureflagshq/python-sdk/workflows/CI/badge.svg)](https://github.com/featureflagshq/python-sdk/actions)
[![Coverage Status](https://codecov.io/gh/featureflagshq/python-sdk/branch/main/graph/badge.svg)](https://codecov.io/gh/featureflagshq/python-sdk)
[![Security Rating](https://img.shields.io/badge/security-A+-brightgreen)](https://github.com/featureflagshq/python-sdk/security)

Official Python SDK for **FeatureFlagsHQ** - Enterprise feature flag management with advanced security, targeting, and analytics.

## 🚀 Features

- **Enterprise Security**: HMAC authentication, rate limiting, circuit breakers
- **Advanced Targeting**: User segments, percentage rollouts, sticky sessions  
- **Real-time Updates**: Background polling with configurable intervals
- **Comprehensive Analytics**: User access logs, performance metrics, security events
- **Type Safety**: Full type hints and mypy compatibility
- **Framework Agnostic**: Works with Django, Flask, FastAPI, and more
- **Production Ready**: Memory monitoring, graceful shutdown, error handling

## 📦 Installation

```bash
pip install featureflagshq
```

### Optional Dependencies

```bash
# For development
pip install featureflagshq[dev]

# For testing  
pip install featureflagshq[test]

# For documentation
pip install featureflagshq[docs]
```

## 🔧 Quick Start

```python
import featureflagshq

# Initialize the client
client = featureflagshq.create_client(
    client_id="your-client-id",
    client_secret="your-client-secret",
    environment="production"
)

# Check if feature is enabled for user
if client.is_flag_enabled_for_user("user123", "new_dashboard"):
    # Show new dashboard
    render_new_dashboard()
else:
    # Show old dashboard  
    render_old_dashboard()

# Get different types of flags
max_items = client.get_int("user123", "max_items", default_value=10)
welcome_msg = client.get_string("user123", "welcome_message", default_value="Hello!")
config = client.get_json("user123", "ui_config", default_value={})

# Use with segments for advanced targeting
segments = {
    "subscription": "premium", 
    "region": "us-west",
    "device": "mobile"
}
premium_feature = client.get_bool("user123", "premium_feature", segments=segments)
```

## 🎯 Advanced Usage

### Context Manager (Recommended)

```python
with featureflagshq.create_client("client-id", "client-secret") as client:
    enabled = client.is_flag_enabled_for_user("user123", "feature")
    # Client automatically shuts down when exiting context
```

### Batch Flag Evaluation

```python
# Get multiple flags at once
user_flags = client.get_user_flags(
    user_id="user123",
    segments={"subscription": "premium"},
    flag_keys=["feature_a", "feature_b", "feature_c"]  # optional filter
)

for flag_name, flag_value in user_flags.items():
    print(f"{flag_name}: {flag_value}")
```

### Custom Configuration

```python
client = featureflagshq.FeatureFlagsHQSDK(
    api_base_url="https://api.featureflagshq.com",
    client_id="your-client-id",
    client_secret="your-client-secret",
    environment="production",
    polling_interval=300,        # 5 minutes
    timeout=30,                  # 30 seconds
    max_retries=3,              # Retry failed requests
    enable_metrics=True,         # Analytics and logging
    debug=False,                # Debug mode
    offline_mode=False,         # Offline testing
    custom_headers={"Custom-Header": "value"}
)
```

## 🏗️ Framework Integration

### Django

```python
# settings.py
FEATUREFLAGSHQ_CLIENT_ID = "your-client-id"
FEATUREFLAGSHQ_CLIENT_SECRET = "your-client-secret"

# Initialize in apps.py or middleware
from django.apps import AppConfig
import featureflagshq

class MyAppConfig(AppConfig):
    def ready(self):
        self.feature_flags = featureflagshq.create_client(
            client_id=settings.FEATUREFLAGSHQ_CLIENT_ID,
            client_secret=settings.FEATUREFLAGSHQ_CLIENT_SECRET
        )

# Use in views
def my_view(request):
    if app_config.feature_flags.is_flag_enabled_for_user(
        str(request.user.id), 
        "new_feature"
    ):
        return render(request, 'new_template.html')
    return render(request, 'old_template.html')
```

### Flask

```python
from flask import Flask, g
import featureflagshq

app = Flask(__name__)

@app.before_first_request
def init_feature_flags():
    app.feature_flags = featureflagshq.create_client(
        client_id=app.config['FEATUREFLAGSHQ_CLIENT_ID'],
        client_secret=app.config['FEATUREFLAGSHQ_CLIENT_SECRET']
    )

@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if app.feature_flags.is_flag_enabled_for_user(user_id, "new_dashboard"):
        return render_template('new_dashboard.html')
    return render_template('old_dashboard.html')
```

### FastAPI

```python
from fastapi import FastAPI, Depends
import featureflagshq

app = FastAPI()

# Initialize client
feature_flags = featureflagshq.create_client(
    client_id="your-client-id",
    client_secret="your-client-secret"
)

async def get_feature_flags():
    return feature_flags

@app.get("/api/dashboard")
async def get_dashboard(
    user_id: str,
    flags: featureflagshq.FeatureFlagsHQSDK = Depends(get_feature_flags)
):
    if flags.is_flag_enabled_for_user(user_id, "new_api"):
        return {"version": "v2", "features": ["advanced"]}
    return {"version": "v1", "features": ["basic"]}
```

## 🔐 Security Features

- **HMAC Authentication**: Cryptographic request signing
- **Rate Limiting**: Per-user request throttling  
- **Input Validation**: Sanitization and bounds checking
- **Circuit Breaker**: Automatic failure recovery
- **Security Logging**: Audit trail for suspicious activity
- **Memory Protection**: Automatic cleanup and monitoring

## 📊 Analytics & Monitoring

```python
# Get comprehensive stats
stats = client.get_stats()
print(f"Total evaluations: {stats['total_user_accesses']}")
print(f"Avg evaluation time: {stats['evaluation_times']['avg_ms']}ms")

# Health check
health = client.get_health_check()
print(f"Status: {health['status']}")
print(f"Cached flags: {health['cached_flags_count']}")

# Security metrics
security_stats = client.get_security_stats()
print(f"Blocked requests: {security_stats['blocked_malicious_requests']}")
```

## 🧪 Testing

### Unit Testing with Mock Client

```python
import pytest
from unittest.mock import Mock
import featureflagshq

def test_feature_enabled():
    # Mock the client
    mock_client = Mock(spec=featureflagshq.FeatureFlagsHQSDK)
    mock_client.is_flag_enabled_for_user.return_value = True
    
    # Test your code
    result = my_function_that_uses_flags(mock_client)
    assert result == "new_feature_result"

def test_with_offline_mode():
    # Use offline mode for testing
    client = featureflagshq.create_client(
        client_id="test-id",
        client_secret="test-secret", 
        offline_mode=True
    )
    
    # Will return default values
    enabled = client.is_flag_enabled_for_user("test-user", "test-flag")
    assert enabled == False  # Default for boolean flags
```

## 📖 API Reference

### Main Client Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `get(user_id, flag_key, default_value, segments)` | Get flag value with type auto-detection | `Any` |
| `get_bool(user_id, flag_key, default_value, segments)` | Get boolean flag | `bool` |
| `get_string(user_id, flag_key, default_value, segments)` | Get string flag | `str` |
| `get_int(user_id, flag_key, default_value, segments)` | Get integer flag | `int` |
| `get_float(user_id, flag_key, default_value, segments)` | Get float flag | `float` |
| `get_json(user_id, flag_key, default_value, segments)` | Get JSON object flag | `dict` |
| `is_flag_enabled_for_user(user_id, flag_key, segments)` | Check if flag is enabled | `bool` |
| `get_user_flags(user_id, segments, flag_keys)` | Get multiple flags | `Dict[str, Any]` |

### Management Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `refresh_flags()` | Manually refresh flags | `bool` |
| `get_all_flags()` | Get all cached flags | `Dict[str, Dict]` |
| `get_stats()` | Get usage statistics | `Dict` |
| `get_health_check()` | Get system health | `Dict` |
| `flush_logs()` | Upload pending logs | `bool` |
| `shutdown()` | Graceful shutdown | `None` |

## 🔧 Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client_id` | `str` | Required | Your FeatureFlagsHQ client ID |
| `client_secret` | `str` | Required | Your FeatureFlagsHQ client secret |
| `api_base_url` | `str` | `https://api.featureflagshq.com` | API endpoint |
| `environment` | `str` | `production` | Environment name |
| `polling_interval` | `int` | `300` | Background sync interval (seconds) |
| `log_upload_interval` | `int` | `120` | Log upload interval (seconds) |
| `timeout` | `int` | `30` | Request timeout (seconds) |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `enable_metrics` | `bool` | `True` | Enable analytics collection |
| `offline_mode` | `bool` | `False` | Disable API calls (testing) |
| `debug` | `bool` | `False` | Enable debug logging |

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/featureflagshq/python-sdk.git
cd python-sdk

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev,test,docs]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run linting
black src tests
isort src tests
flake8 src tests
mypy src
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [GitHub](https://github.com/featureflagshq/python-sdk)
- **Issues**: [GitHub Issues](https://github.com/featureflagshq/python-sdk/issues)
- **Security**: [Security Policy](SECURITY.md)
- **Email**: [hello@featureflagshq.com](mailto:hello@featureflagshq.com)

## 🗺️ Roadmap

- [ ] Async/await support
- [ ] Redis caching backend
- [ ] Streaming real-time updates
- [ ] Advanced A/B testing utilities
- [ ] Multi-environment configuration
- [ ] Custom targeting rules engine

---

**Built with ❤️ by the FeatureFlagsHQ Team**