# Contributing to FeatureFlagsHQ Python SDK

Thank you for your interest in contributing to the FeatureFlagsHQ Python SDK! We welcome contributions from the community and appreciate your help in making feature flag management better for Python developers.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Community and Support](#community-and-support)

## Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please be respectful, inclusive, and constructive in all interactions.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python** 3.8 or higher
- **pip** package manager
- **Git** installed and configured
- Basic familiarity with feature flags and Python development
- Understanding of REST APIs and SDK patterns

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/python-sdk.git
   cd python-sdk
   ```
3. Add the upstream repository as a remote:
   ```bash
   git remote add upstream https://github.com/featureflagshq/python-sdk.git
   ```

## Development Setup

### Using pip and venv

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Environment Setup

1. Set up your FeatureFlagsHQ credentials for testing:
   ```bash
   export FEATUREFLAGSHQ_CLIENT_ID="your-test-client-id"
   export FEATUREFLAGSHQ_CLIENT_SECRET="your-test-client-secret"
   ```

3. Run tests to ensure everything works:
   ```bash
   pytest
   ```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes** - Fix issues in the SDK functionality
- **Feature additions** - Add new feature flag capabilities
- **Performance optimizations** - Improve SDK performance and caching
- **Documentation improvements** - Enhance README, API docs, or examples
- **Test coverage** - Add or improve test cases
- **Examples and tutorials** - Create usage examples for different frameworks
- **Framework integrations** - Improve integration examples for Django, Flask, etc.

### Before You Start

1. **Check existing issues** - Look for related issues or feature requests
2. **Create an issue** - For significant changes, create an issue first to discuss the approach
3. **Get feedback** - Engage with maintainers to align on the solution
4. **Consider SDK design** - Ensure changes align with SDK principles of simplicity and reliability

## Pull Request Process

### Creating a Pull Request

1. **Create a feature branch** from `master`:
   ```bash
   git checkout -b feature/add-batch-evaluation
   # or
   git checkout -b fix/cache-invalidation-bug
   ```

2. **Make your changes** following our coding standards

3. **Write or update tests** for your changes

4. **Update documentation** if needed

5. **Run the full test suite**:
   ```bash
   pytest --cov=featureflagshq
   ```

6. **Commit your changes** with descriptive messages:
   ```bash
   git commit -m "feat: add batch flag evaluation support"
   git commit -m "fix: resolve cache invalidation in local mode"
   ```

7. **Push to your fork**:
   ```bash
   git push origin feature/add-batch-evaluation
   ```

8. **Open a pull request** on `staging` branch with:
   - Clear title and description
   - Reference to related issues (e.g., "Closes #123")
   - Examples of the new functionality
   - Breaking change notes if applicable

### Pull Request Requirements

Before submitting, ensure your PR:

- ✅ Passes all tests (`pytest`)
- ✅ Follows coding standards (`black`, `isort`, `flake8`)
- ✅ Has appropriate test coverage (minimum 90%)
- ✅ Updates documentation if needed
- ✅ Includes clear commit messages
- ✅ Has no merge conflicts with `main`
- ✅ Maintains backward compatibility (unless breaking change is justified)

### Review Process

1. **Automated checks** - GitHub Actions runs tests, linting, and security checks
2. **Code review** - Maintainers review for quality, design, and SDK best practices
3. **Feedback incorporation** - Address any requested changes
4. **Approval and merge** - Once approved, maintainers will merge

## Coding Standards

### Code Style

We use automated tools to maintain consistent code style:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

Run formatting and linting:
```bash
black featureflagshq/ tests/
isort featureflagshq/ tests/
flake8 featureflagshq/ tests/
mypy featureflagshq/
```

### Naming Conventions

- **Modules/Files**: Use snake_case (`feature_client.py`)
- **Classes**: Use PascalCase (`FeatureFlagClient`)
- **Functions/Variables**: Use snake_case (`get_flag_value`)
- **Constants**: Use SCREAMING_SNAKE_CASE (`DEFAULT_TIMEOUT`)
- **Private methods**: Prefix with underscore (`_validate_config`)

### Type Hints

Always use type hints for better code clarity and IDE support:

```python
from typing import Dict, Optional, Union, Any

def get_bool(
    self,
    user_id: str,
    flag_name: str,
    default_value: bool = False,
    segments: Optional[Dict[str, Any]] = None
) -> bool:
    """Get a boolean feature flag value for a user."""
    pass
```

### Error Handling

- Create custom exception classes inheriting from base exceptions
- Provide meaningful error messages
- Include error codes for programmatic handling
- Always handle network timeouts and API errors gracefully

```python
class FeatureFlagsHQError(Exception):
    """Base exception for FeatureFlagsHQ SDK errors."""
    pass

class APIError(FeatureFlagsHQError):
    """Raised when API requests fail."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
```

### Documentation Standards

- Use **Google-style docstrings** for all public functions and classes
- Include parameter types, return types, and example usage
- Document exceptions that may be raised

```python
def get_bool(self, user_id: str, flag_name: str, default_value: bool = False, segments: Optional[Dict[str, Any]] = None) -> bool:
    """Get the boolean value of a feature flag for a specific user.
    
    Args:
        user_id: The unique identifier for the user
        flag_name: The unique identifier for the feature flag
        default_value: Default value to return if flag evaluation fails
        segments: User segments for targeting
        
    Returns:
        The evaluated flag value (True/False)
        
    Raises:
        APIError: If the API request fails
        ValueError: If user_id or flag_name is invalid
        
    Example:
        >>> sdk = FeatureFlagsHQSDK(client_id="your-id", client_secret="your-secret")
        >>> is_enabled = sdk.get_bool("user123", "new-checkout")
        >>> if is_enabled:
        ...     # Show new checkout flow
    """
```

## Testing Guidelines

### Test Structure

- Use **pytest** as the testing framework
- Organize tests in the `tests/` directory mirroring the source structure
- Use **unittest.mock** for mocking external dependencies
- Include both unit tests and integration tests

### Test Categories

1. **Unit Tests** - Test individual functions and classes in isolation
2. **Integration Tests** - Test SDK interaction with FeatureFlagsHQ API
3. **Performance Tests** - Verify SDK performance benchmarks
4. **Framework Tests** - Test integration with Django, Flask, FastAPI

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch
from featureflagshq import FeatureFlagsHQSDK

class TestFeatureFlagsHQSDK:
    def test_get_bool_success(self):
        """Test successful flag evaluation."""
        sdk = FeatureFlagsHQSDK(client_id="test-id", client_secret="test-secret")
        
        with patch.object(sdk, '_make_request') as mock_request:
            mock_request.return_value = {"value": True}
            
            result = sdk.get_bool("user123", "test-flag")
            assert result is True
    
    def test_get_bool_with_default(self):
        """Test flag evaluation returns default on error."""
        sdk = FeatureFlagsHQSDK(client_id="test-id", client_secret="test-secret")
        
        with patch.object(sdk, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            result = sdk.get_bool("user123", "test-flag", default_value=True)
            assert result is True
```

### Test Coverage

- Maintain **minimum 90% test coverage**
- Run coverage reports:
  ```bash
  pytest --cov=featureflagshq --cov-report=html
  ```
- Focus on testing edge cases and error conditions
- Mock external API calls to ensure reliable tests

## Documentation

### API Documentation

- Update docstrings for any new or modified public methods
- Include practical examples in docstrings
- Document breaking changes in method signatures

### README Updates

Update the main README.md when adding:
- New installation methods
- New configuration options
- New framework integrations
- Breaking changes

### Examples

Add examples to the `examples/` directory for:
- New SDK features
- Framework integrations (Django, Flask, FastAPI)
- Common use cases and patterns

## Issue Reporting

### Bug Reports

When reporting bugs, include:

- **Python version** and operating system
- **SDK version** you're using
- **Minimal code example** that reproduces the issue
- **Expected behavior** vs actual behavior
- **Error messages** and stack traces
- **Steps to reproduce** the issue

### Feature Requests

For feature requests, describe:

- **Use case** - What problem does this solve?
- **Proposed solution** - How should it work?
- **Alternatives considered** - What other approaches did you consider?
- **Impact** - Who would benefit from this feature?

### Security Issues

For security vulnerabilities:
- **Do not** create public issues
- Email hello@featureflagshq.com with details
- Include steps to reproduce and potential impact

## Coding Guidelines Specific to Feature Flags

### SDK Design Principles

1. **Fail gracefully** - Always return default values when API is unavailable
2. **Performance first** - Cache aggressively, minimize API calls
3. **Simple API** - Keep the public interface intuitive and minimal
4. **Framework agnostic** - Core SDK should work without web frameworks
5. **Configurable** - Allow customization of timeouts, retry logic, caching

### Feature Flag Best Practices

- **Default values** - Always require default values for flag evaluations
- **User context** - Support rich user context for targeting
- **Caching** - Implement intelligent caching to reduce latency
- **Fallback mode** - Work offline with cached values when possible
- **Logging** - Provide configurable logging for debugging

### Breaking Changes

- Avoid breaking changes when possible
- If breaking changes are necessary:
  - Increment major version
  - Provide migration guide
  - Deprecate old methods before removing
  - Update all examples and documentation

## Development Workflow

### Syncing with Upstream

Regularly sync your fork with the upstream repository:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

### Pre-commit Hooks

Set up pre-commit hooks to automatically run formatting and linting:

```bash
pip install pre-commit
pre-commit install
```

### Release Process

For maintainers releasing new versions:

1. Update version in `featureflagshq/__init__.py`
2. Update `changelog.md`
3. Create release PR
4. Tag release after merge
5. Publish to PyPI

## Community and Support

### Getting Help

- **Documentation**: Check our [official docs](https://featureflagshq.com/documentation/)
- **Issues**: Search existing GitHub issues
- **Discussions**: Use GitHub Discussions for questions
- **Discord**: Join our community Discord server

### Communication

- Be patient and respectful in all interactions
- Provide context when asking questions
- Search existing discussions before asking
- Help others when you can

---

Thank you for contributing to FeatureFlagsHQ! Your efforts help make feature flag management better for the entire Python community. 🚀

For questions about contributing, reach out to us at hello@featureflagshq.com or open a GitHub Discussion.