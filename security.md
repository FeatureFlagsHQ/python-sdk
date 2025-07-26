# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

The FeatureFlagsHQ team takes security bugs seriously. We appreciate your efforts to responsibly disclose your findings, and will make every effort to acknowledge your contributions.

### How to Report Security Issues

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **hello@featureflagshq.com**

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

### What to Include

Please include the following information along with your report:

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

### Preferred Languages

We prefer all communications to be in English.

## Security Features

The FeatureFlagsHQ Python SDK includes several security features:

### Authentication & Authorization
- **HMAC-SHA256 Signatures**: All API requests are signed using HMAC-SHA256 with client credentials
- **Timestamp Validation**: Requests include timestamps to prevent replay attacks
- **Client ID Validation**: Each request includes a client ID for identification

### Input Validation & Sanitization
- **User ID Validation**: Strict validation of user identifiers to prevent injection attacks
- **Flag Key Validation**: Alphanumeric validation for feature flag keys
- **Segment Sanitization**: Input sanitization for user segments and targeting data
- **Length Limits**: Enforced maximum lengths for all user inputs

### Rate Limiting & DoS Protection
- **Per-User Rate Limiting**: Configurable rate limits per user to prevent abuse
- **Circuit Breaker**: Automatic failure recovery to prevent cascading failures
- **Memory Monitoring**: Automatic memory usage monitoring and cleanup

### Data Protection
- **Sensitive Data Filtering**: Automatic redaction of sensitive data in logs
- **Secure Headers**: Sensitive headers are never logged in debug mode
- **Memory Safety**: Automatic cleanup of sensitive data from memory

### Network Security
- **HTTPS Enforcement**: All API communications use HTTPS
- **URL Validation**: Strict validation of API endpoints
- **Connection Pooling**: Secure connection reuse with proper SSL verification

## Security Best Practices

### For SDK Users

1. **Protect Your Credentials**
   ```python
   # ✅ Good - Use environment variables
   import os
   client = featureflagshq.create_client(
       client_id=os.getenv('FEATUREFLAGSHQ_CLIENT_ID'),
       client_secret=os.getenv('FEATUREFLAGSHQ_CLIENT_SECRET')
   )
   
   # ❌ Bad - Hard-coded credentials
   client = featureflagshq.create_client(
       client_id="your-client-id",
       client_secret="your-client-secret"
   )
   ```

2. **Use Context Managers**
   ```python
   # ✅ Good - Automatic cleanup
   with featureflagshq.create_client(client_id, client_secret) as client:
       result = client.get_bool("user123", "feature")
   
   # ❌ Less secure - Manual cleanup required
   client = featureflagshq.create_client(client_id, client_secret)
   result = client.get_bool("user123", "feature")
   client.shutdown()  # Must remember to call this
   ```

3. **Validate User Input**
   ```python
   # ✅ Good - Validate user input
   def get_feature_for_user(user_input):
       if not user_input or len(user_input) > 256:
           raise ValueError("Invalid user ID")
       return client.get_bool(user_input, "feature")
   
   # ❌ Bad - Direct use of user input
   def get_feature_for_user(user_input):
       return client.get_bool(user_input, "feature")
   ```

4. **Use Offline Mode for Testing**
   ```python
   # ✅ Good - Use offline mode in tests
   def test_feature_logic():
       client = featureflagshq.create_client(
           "test-id", "test-secret", offline_mode=True
       )
       # Test your logic without making API calls
   ```

5. **Monitor Security Events**
   ```python
   # ✅ Good - Monitor security statistics
   stats = client.get_security_stats()
   if stats['blocked_malicious_requests'] > 0:
       logger.warning(f"Blocked {stats['blocked_malicious_requests']} malicious requests")
   ```

### For Production Deployments

1. **Network Security**
   - Always use HTTPS endpoints
   - Consider using a private network or VPN for API access
   - Implement proper firewall rules

2. **Credential Management**
   - Use environment variables or secure secret management systems
   - Rotate credentials regularly
   - Use different credentials for different environments

3. **Monitoring & Alerting**
   - Monitor for unusual API usage patterns
   - Set up alerts for security events
   - Regularly review access logs

4. **Resource Limits**
   - Set appropriate timeout values
   - Configure memory limits for your application
   - Monitor CPU and memory usage

## Vulnerability Disclosure Timeline

1. **Day 0**: Security vulnerability reported
2. **Day 1-2**: Initial response and acknowledgment
3. **Day 3-7**: Vulnerability assessment and reproduction
4. **Day 8-30**: Patch development and testing
5. **Day 31-60**: Patch deployment and public disclosure
6. **Day 61+**: Post-disclosure monitoring and follow-up

## Security Contact Information

- **Email**: hello@featureflagshq.com
- **PGP Key**: Available upon request
- **Response Time**: Within 48 hours

## Acknowledgments

We would like to thank the following researchers for their responsible disclosure of security vulnerabilities:

- *No vulnerabilities reported yet*

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Python Security Documentation](https://docs.python.org/3/library/security_warnings.html)

---

**Last Updated**: January 26, 2025  
**Next Review**: April 26, 2025