#!/bin/bash
# FeatureFlagsHQ Python SDK - Test Script

set -e

echo "🧪 Testing FeatureFlagsHQ Python SDK"
echo "==================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    print_error "pytest is not installed. Installing..."
    pip install pytest pytest-cov pytest-mock
fi

# Set test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Default test options
TEST_ARGS=""
COVERAGE_ARGS="--cov=featureflagshq --cov-report=term-missing --cov-report=html --cov-report=xml"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            TEST_ARGS="$TEST_ARGS tests/unit/"
            shift
            ;;
        --integration)
            TEST_ARGS="$TEST_ARGS tests/integration/"
            shift
            ;;
        --security)
            TEST_ARGS="$TEST_ARGS -m security"
            shift
            ;;
        --no-cov)
            COVERAGE_ARGS=""
            shift
            ;;
        --fast)
            TEST_ARGS="$TEST_ARGS -x --tb=short"
            shift
            ;;
        --verbose)
            TEST_ARGS="$TEST_ARGS -v"
            shift
            ;;
        --debug)
            TEST_ARGS="$TEST_ARGS -s --tb=long"
            shift
            ;;
        *)
            TEST_ARGS="$TEST_ARGS $1"
            shift
            ;;
    esac
done

# Set default test path if none specified
if [[ ! "$TEST_ARGS" =~ tests/ ]]; then
    TEST_ARGS="$TEST_ARGS tests/"
fi

print_status "Test configuration:"
echo "  Test arguments: $TEST_ARGS"
echo "  Coverage arguments: $COVERAGE_ARGS"
echo "  Python path: $PYTHONPATH"

# Create test reports directory
mkdir -p reports

# Run the tests
print_status "Running tests..."
pytest $TEST_ARGS $COVERAGE_ARGS \
    --junitxml=reports/junit.xml \
    --tb=short \
    || {
    print_error "Tests failed!"
    exit 1
}

print_success "All tests passed! ✅"

# Generate coverage badge if coverage was run
if [[ "$COVERAGE_ARGS" != "" ]] && command -v coverage-badge &> /dev/null; then
    print_status "Generating coverage badge..."
    coverage-badge -o coverage.svg
    print_success "Coverage badge generated"
fi

# Show coverage summary
if [ -f ".coverage" ]; then
    print_status "Coverage summary:"
    coverage report --show-missing
fi

# Check coverage threshold
if [ -f ".coverage" ]; then
    coverage_percent=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
    threshold=80
    
    if [ "${coverage_percent%.*}" -lt "$threshold" ]; then
        print_warning "Coverage is below $threshold% (current: $coverage_percent%)"
    else
        print_success "Coverage is above $threshold% (current: $coverage_percent%)"
    fi
fi

print_status "Test reports generated in reports/ directory"
if [ -f "htmlcov/index.html" ]; then
    print_status "HTML coverage report: htmlcov/index.html"
fi