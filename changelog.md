# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-08-03

### Added
- Enterprise-grade security with HMAC authentication
- Advanced input validation and sanitization
- Circuit breaker pattern for resilient API calls
- User segmentation support for advanced targeting
- Background polling for real-time flag updates
- Comprehensive analytics and metrics collection
- Rate limiting per user to prevent abuse
- Offline mode support for degraded environments
- Flag change callbacks for real-time notifications
- Context manager support for automatic cleanup
- Production-ready configuration helpers
- Extensive logging with security filtering
- Memory management and cleanup utilities
- Health check and diagnostics endpoints

### Security
- HMAC-SHA256 signed API requests
- Input validation against injection attacks
- Sensitive data filtering in logs
- Secure credential handling
- Protection against malicious inputs
- Initialization parameters for enhanced security
- Method signatures for user segmentation

### Performance
- Background flag polling (5-minute intervals)
- Local caching with thread-safe access
- Automatic retry logic with exponential backoff
- Connection pooling for HTTP requests
- Memory-efficient statistics tracking

### Basic
- Basic feature flag evaluation
- Simple API integration
- Basic error handling