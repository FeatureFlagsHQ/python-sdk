#!/bin/bash
# FeatureFlagsHQ Python SDK - Build Script

set -e  # Exit on any error

echo "🏗️  Building FeatureFlagsHQ Python SDK"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "pyproject.toml not found. Please run from the project root directory."
    exit 1
fi

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/ || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
print_status "Using Python version: $python_version"

# Verify minimum Python version (3.8+)
python3 -c "import sys; assert sys.version_info >= (3, 8), 'Python 3.8+ required'" || {
    print_error "Python 3.8 or higher is required"
    exit 1
}

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "No virtual environment detected. Consider using one for isolation."
fi

# Install/upgrade build dependencies
print_status "Installing build dependencies..."
python3 -m pip install --upgrade pip build twine wheel setuptools

# Verify package structure
print_status "Verifying package structure..."
if [ ! -d "src/featureflagshq" ]; then
    print_error "src/featureflagshq directory not found"
    exit 1
fi

if [ ! -f "src/featureflagshq/__init__.py" ]; then
    print_error "src/featureflagshq/__init__.py not found"
    exit 1
fi

# Run code quality checks
print_status "Running code quality checks..."

# Format check
if command -v black &> /dev/null; then
    print_status "Checking code formatting with black..."
    black --check src tests || {
        print_error "Code formatting issues found. Run 'black src tests' to fix."
        exit 1
    }
    print_success "Code formatting is correct"
else
    print_warning "black not found, skipping format check"
fi

# Import sorting check
if command -v isort &> /dev/null; then
    print_status "Checking import sorting with isort..."
    isort --check-only src tests || {
        print_error "Import sorting issues found. Run 'isort src tests' to fix."
        exit 1
    }
    print_success "Import sorting is correct"
else
    print_warning "isort not found, skipping import sort check"
fi

# Linting
if command -v flake8 &> /dev/null; then
    print_status "Running linting with flake8..."
    flake8 src tests || {
        print_error "Linting issues found. Please fix them before building."
        exit 1
    }
    print_success "Linting passed"
else
    print_warning "flake8 not found, skipping linting"
fi

# Type checking
if command -v mypy &> /dev/null; then
    print_status "Running type checking with mypy..."
    mypy src/featureflagshq || {
        print_error "Type checking failed. Please fix type issues before building."
        exit 1
    }
    print_success "Type checking passed"
else
    print_warning "mypy not found, skipping type checking"
fi

# Security check
if command -v bandit &> /dev/null; then
    print_status "Running security scan with bandit..."
    bandit -r src/featureflagshq/ -ll || {
        print_error "Security issues found. Please review and fix."
        exit 1
    }
    print_success "Security scan passed"
else
    print_warning "bandit not found, skipping security scan"
fi

# Run tests
print_status "Running tests..."
if command -v pytest &> /dev/null; then
    pytest tests/ --tb=short || {
        print_error "Tests failed. Please fix failing tests before building."
        exit 1
    }
    print_success "All tests passed"
else
    print_warning "pytest not found, skipping tests"
fi

# Check package metadata
print_status "Validating package metadata..."
python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    config = tomllib.load(f)
    
# Validate required fields
project = config.get('project', {})
required_fields = ['name', 'description', 'authors', 'requires-python', 'dependencies']

for field in required_fields:
    if field not in project:
        raise ValueError(f'Missing required field: project.{field}')

print('✓ Package metadata is valid')
"

# Build the package
print_status "Building source and wheel distributions..."
python3 -m build

# Verify the build
print_status "Verifying build artifacts..."
if [ ! -d "dist" ]; then
    print_error "dist directory not created"
    exit 1
fi

# Count distribution files
sdist_count=$(find dist -name "*.tar.gz" | wc -l)
wheel_count=$(find dist -name "*.whl" | wc -l)

if [ "$sdist_count" -eq 0 ]; then
    print_error "Source distribution not created"
    exit 1
fi

if [ "$wheel_count" -eq 0 ]; then
    print_error "Wheel distribution not created"
    exit 1
fi

print_success "Created $sdist_count source distribution(s) and $wheel_count wheel(s)"

# Check distribution with twine
print_status "Checking distributions with twine..."
python3 -m twine check dist/* || {
    print_error "Distribution check failed"
    exit 1
}

# Display package information
print_status "Package information:"
python3 -c "
from src.featureflagshq._version import __version__, __description__
print(f'  Name: featureflagshq')
print(f'  Version: {__version__}')
print(f'  Description: {__description__}')
"

# List distribution files
print_status "Built distributions:"
ls -la dist/

# Calculate file sizes
print_status "Distribution sizes:"
du -h dist/*

print_success "Build completed successfully! 🎉"
print_status "Next steps:"
echo "  1. Test the package: pip install dist/*.whl"
echo "  2. Publish to TestPyPI: python -m twine upload --repository testpypi dist/*"
echo "  3. Publish to PyPI: python -m twine upload dist/*"