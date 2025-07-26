#!/bin/bash
# FeatureFlagsHQ Python SDK - Release Script

set -e

echo "🚀 FeatureFlagsHQ Python SDK Release"
echo "===================================="

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

# Function to prompt for confirmation
confirm() {
    read -p "$1 (y/N): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Check if we're on the main branch
current_branch=$(git branch --show-current)
if [ "$current_branch" != "main" ]; then
    print_warning "You're not on the main branch (current: $current_branch)"
    if ! confirm "Continue anyway?"; then
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff --quiet HEAD; then
    print_error "You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

# Get current version
current_version=$(python3 -c "from src.featureflagshq._version import __version__; print(__version__)")
print_status "Current version: $current_version"

# Parse release type
release_type=${1:-patch}
case $release_type in
    major|minor|patch)
        ;;
    *)
        print_error "Invalid release type. Use: major, minor, or patch"
        exit 1
        ;;
esac

# Calculate new version (simplified - you might want to use a proper tool like bumpversion)
IFS='.' read -r -a version_parts <<< "$current_version"
major=${version_parts[0]}
minor=${version_parts[1]}
patch=${version_parts[2]}

case $release_type in
    major)
        major=$((major + 1))
        minor=0
        patch=0
        ;;
    minor)
        minor=$((minor + 1))
        patch=0
        ;;
    patch)
        patch=$((patch + 1))
        ;;
esac

new_version="$major.$minor.$patch"
print_status "New version will be: $new_version"

if ! confirm "Proceed with release $new_version?"; then
    print_status "Release cancelled"
    exit 0
fi

# Update version file
print_status "Updating version file..."
sed -i.bak "s/__version__ = \"$current_version\"/__version__ = \"$new_version\"/" src/featureflagshq/_version.py
rm -f src/featureflagshq/_version.py.bak

# Update release date in version file
current_date=$(date '+%Y-%m-%d')
sed -i.bak "s/__release_date__ = \".*\"/__release_date__ = \"$current_date\"/" src/featureflagshq/_version.py
rm -f src/featureflagshq/_version.py.bak

# Run full test suite
print_status "Running full test suite..."
./scripts/test.sh --fast || {
    print_error "Tests failed. Release aborted."
    # Restore version file
    git checkout src/featureflagshq/_version.py
    exit 1
}

# Run security scan
print_status "Running security scan..."
if command -v bandit &> /dev/null; then
    bandit -r src/featureflagshq/ || {
        print_error "Security scan failed. Release aborted."
        git checkout src/featureflagshq/_version.py
        exit 1
    }
fi

# Build package
print_status "Building package..."
./scripts/build.sh || {
    print_error "Build failed. Release aborted."
    git checkout src/featureflagshq/_version.py
    exit 1
}

# Update changelog
print_status "Updating CHANGELOG.md..."
changelog_entry="## [$new_version] - $current_date

### Added
- Release $new_version

### Changed
- Version bump to $new_version

### Fixed
- Bug fixes and improvements
"

# Insert changelog entry after the [Unreleased] section
awk -v entry="$changelog_entry" '
/^## \[Unreleased\]/ {
    print $0
    print ""
    print entry
    next
}
{print}
' CHANGELOG.md > CHANGELOG.md.tmp && mv CHANGELOG.md.tmp CHANGELOG.md

print_status "Please update CHANGELOG.md with actual changes for this release"
if confirm "Open CHANGELOG.md for editing?"; then
    ${EDITOR:-nano} CHANGELOG.md
fi

# Commit changes
print_status "Committing changes..."
git add src/featureflagshq/_version.py CHANGELOG.md
git commit -m "Release v$new_version

- Bump version to $new_version
- Update changelog for release
"

# Create tag
print_status "Creating release tag..."
git tag -a "v$new_version" -m "Release v$new_version"

# Push to repository
if confirm "Push to repository?"; then
    print_status "Pushing to repository..."
    git push origin main
    git push origin "v$new_version"
    print_success "Changes pushed to repository"
fi

# Publish to TestPyPI first
if confirm "Publish to TestPyPI for testing?"; then
    print_status "Publishing to TestPyPI..."
    python3 -m twine upload --repository testpypi dist/* || {
        print_error "TestPyPI upload failed"
        exit 1
    }
    print_success "Published to TestPyPI"
    print_status "Test installation: pip install -i https://test.pypi.org/simple/ featureflagshq==$new_version"
    
    if confirm "Test passed? Proceed to PyPI?"; then
        :
    else
        print_warning "Release process stopped before PyPI publication"
        exit 0
    fi
fi

# Publish to PyPI
if confirm "Publish to PyPI?"; then
    print_status "Publishing to PyPI..."
    python3 -m twine upload dist/* || {
        print_error "PyPI upload failed"
        exit 1
    }
    print_success "Published to PyPI! 🎉"
    print_status "Installation: pip install featureflagshq==$new_version"
fi

# Create GitHub release (if gh CLI is available)
if command -v gh &> /dev/null; then
    if confirm "Create GitHub release?"; then
        print_status "Creating GitHub release..."
        gh release create "v$new_version" \
            --title "Release v$new_version" \
            --notes "See CHANGELOG.md for details" \
            dist/* || {
            print_warning "GitHub release creation failed"
        }
    fi
fi

print_success "Release $new_version completed successfully! 🎉"
print_status "Next steps:"
echo "  1. Verify installation: pip install featureflagshq==$new_version"
echo "  2. Update documentation if needed"
echo "  3. Announce the release"
echo "  4. Monitor for issues"