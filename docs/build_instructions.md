# Build and Publish Instructions

## Development Setup

1. **Clone and setup the project:**
```bash
git clone <your-repo-url>
cd featureflagshq-sdk
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .[dev]
```

2. **Install development dependencies:**
```bash
pip install -r requirements-dev.txt
```

## Development Workflow

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=featureflagshq --cov-report=html

# Run specific test file
pytest tests/test_sdk.py

# Run integration tests (requires environment variables)
export FEATUREFLAGSHQ_INTEGRATION_TESTS=1
export FEATUREFLAGSHQ_CLIENT_ID=your_client_id
export FEATUREFLAGSHQ_CLIENT_SECRET=your_client_secret
pytest tests/test_integration.py
```

### Code Quality
```bash
# Format code with black
black featureflagshq/ tests/ examples/

# Lint with flake8
flake8 featureflagshq/ tests/

# Type checking with mypy
mypy featureflagshq/
```

### Running Examples
```bash
# Set environment variables
export FEATUREFLAGSHQ_CLIENT_ID=your_client_id
export FEATUREFLAGSHQ_CLIENT_SECRET=your_client_secret

# Run basic example
python examples/basic_usage.py

# Run advanced example
python examples/advanced_usage.py

# Run Django integration example
python examples/django_integration.py
```

## Building the Package

### 1. Update Version
Update version in `featureflagshq/__init__.py`:
```python
__version__ = "2.0.1"
```

### 2. Update Changelog
Add new version entry to `CHANGELOG.md`:
```markdown
## [2.0.1] - 2024-08-04
### Fixed
- Bug fix description
### Added  
- New feature description
```

### 3. Build Package
```bash
# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Build source and wheel distributions
python -m build

# Or using setup.py
python setup.py sdist bdist_wheel
```

### 4. Check Package
```bash
# Check package integrity
twine check dist/*

# Test installation locally
pip install dist/featureflagshq_sdk-2.0.1-py3-none-any.whl
```

## Publishing to PyPI

### 1. Test on TestPyPI First
```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Install from TestPyPI to test
pip install --index-url https://test.pypi.org/simple/ featureflagshq-sdk
```

### 2. Publish to PyPI
```bash
# Upload to PyPI
twine upload dist/*

# Or specify repository explicitly
twine upload --repository pypi dist/*
```

### 3. Verify Publication
```bash
# Install from PyPI
pip install featureflagshq-sdk

# Check version
python -c "import featureflagshq; print(featureflagshq.__version__)"
```

## PyPI Configuration

### 1. Setup PyPI Account
- Create account at https://pypi.org
- Create account at https://test.pypi.org (for testing)
- Generate API tokens for authentication

### 2. Configure .pypirc
Create `~/.pypirc`:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-api-token-here
```

### 3. Environment Variables (Alternative)
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-api-token-here
```

## Automated CI/CD (GitHub Actions)

Create `.github/workflows/publish.yml`:
```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.8'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    
    - name: Build package
      run: python -m build
    
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

## Release Checklist

### Pre-Release
- [ ] Update version number in `__init__.py`
- [ ] Update `CHANGELOG.md`
- [ ] Run all tests: `pytest`
- [ ] Run code quality checks: `black`, `flake8`, `mypy`
- [ ] Build package: `python -m build`
- [ ] Check package: `twine check dist/*`
- [ ] Test on TestPyPI
- [ ] Test installation from TestPyPI

### Release
- [ ] Create Git tag: `git tag v2.0.1`
- [ ] Push tag: `git push origin v2.0.1`
- [ ] Publish to PyPI: `twine upload dist/*`
- [ ] Create GitHub release
- [ ] Update documentation
- [ ] Announce release

### Post-Release
- [ ] Verify PyPI listing
- [ ] Test installation: `pip install featureflagshq-sdk`
- [ ] Update examples if needed
- [ ] Monitor for issues

## Common Issues and Solutions

### 1. Build Errors
```bash
# Clear build cache
rm -rf build/ dist/ *.egg-info/

# Check setup.py syntax
python setup.py check

# Verbose build
python -m build --verbose
```

### 2. Upload Errors
```bash
# Check package before upload
twine check dist/*

# Upload with verbose output
twine upload --verbose dist/*

# Skip existing files (if re-uploading)
twine upload --skip-existing dist/*
```

### 3. Import Errors
```bash
# Check package structure
python -c "import featureflagshq; print(dir(featureflagshq))"

# Test in clean environment
python -m venv test_env
source test_env/bin/activate
pip install featureflagshq-sdk
python -c "from featureflagshq import FeatureFlagsHQSDK"
```

### 4. Version Conflicts
```bash
# Check current version
pip show featureflagshq-sdk

# Force reinstall
pip install --force-reinstall featureflagshq-sdk

# Install specific version
pip install featureflagshq-sdk==2.0.1
```

## Directory Structure for Package

```
featureflagshq-sdk/
├── featureflagshq/           # Main package
│   ├── __init__.py           # Package initialization
│   └── sdk.py                # Main SDK code
├── tests/                    # Test files
│   ├── __init__.py
│   ├── test_sdk.py
│   └── test_integration.py
├── examples/                 # Usage examples
│   ├── basic_usage.py
│   ├── advanced_usage.py
│   └── django_integration.py
├── docs/                     # Documentation
│   └── API.md
├── setup.py                  # Package setup
├── setup.cfg                 # Setup configuration
├── pyproject.toml           # Modern Python packaging
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Development dependencies
├── README.md                # Package description
├── LICENSE                  # License file
├── CHANGELOG.md             # Version history
├── MANIFEST.in              # Include additional files
└── .gitignore              # Git ignore rules
```

## Package Metadata Verification

Before publishing, verify all metadata is correct:

```bash
# Check package info
python setup.py --name
python setup.py --version
python setup.py --author
python setup.py --description
python setup.py --url
python setup.py --license
python setup.py --classifiers
```

## Testing Package Installation

```bash
# Create fresh virtual environment
python -m venv test_install
source test_install/bin/activate

# Install from PyPI
pip install featureflagshq-sdk

# Test basic functionality
python -c "
from featureflagshq import FeatureFlagsHQSDK
print('SDK imported successfully')
print('Version:', featureflagshq.__version__)
"

# Test with actual usage
python examples/basic_usage.py
```

## Monitoring and Maintenance

### After Publication
- Monitor PyPI download statistics
- Watch for user issues and bug reports
- Keep dependencies updated
- Monitor security vulnerabilities
- Plan regular releases

### Version Management
- Follow semantic versioning (MAJOR.MINOR.PATCH)
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)  
- PATCH: Bug fixes (backward compatible)

### Documentation Updates
- Keep README.md current
- Update API documentation
- Maintain example code
- Update integration guides