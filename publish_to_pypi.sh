#!/bin/bash

# MultiCord CLI - PyPI Publishing Script
# This script builds and publishes the MultiCord CLI to PyPI

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi

    # Check pip
    if ! command -v pip &> /dev/null; then
        log_error "pip is not installed"
        exit 1
    fi

    # Install build tools if not present
    log_info "Installing/updating build tools..."
    pip install --upgrade build twine

    log_info "Prerequisites check passed!"
}

# Clean previous builds
clean_build() {
    log_info "Cleaning previous builds..."
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info
    rm -rf multicord.egg-info/
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    log_info "Cleaned build artifacts"
}

# Run tests
run_tests() {
    log_info "Running tests..."

    # Install dev dependencies
    pip install -e ".[dev]"

    # Run pytest if tests exist
    if [ -d "tests" ]; then
        pytest tests/ || {
            log_warning "Some tests failed. Continue anyway? (y/n)"
            read -r response
            if [ "$response" != "y" ]; then
                log_error "Aborted due to test failures"
                exit 1
            fi
        }
    else
        log_warning "No tests directory found, skipping tests"
    fi
}

# Build the package
build_package() {
    log_info "Building the package..."

    # Build using the modern build system
    python -m build

    # Check if build was successful
    if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
        log_error "Build failed - no distribution files created"
        exit 1
    fi

    log_info "Package built successfully!"
    ls -la dist/
}

# Check the package
check_package() {
    log_info "Checking the package with twine..."

    # Check the distribution
    twine check dist/*

    # Show package contents
    log_info "Package contents:"
    tar -tzf dist/*.tar.gz | head -20
}

# Upload to Test PyPI (optional)
upload_test_pypi() {
    log_warning "Upload to Test PyPI first? This is recommended for first-time uploads. (y/n)"
    read -r response

    if [ "$response" = "y" ]; then
        log_info "Uploading to Test PyPI..."
        twine upload --repository testpypi dist/*

        echo ""
        log_info "Package uploaded to Test PyPI!"
        log_info "Test installation with:"
        echo "  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ multicord"
        echo ""

        log_warning "Continue with production PyPI upload? (y/n)"
        read -r response
        if [ "$response" != "y" ]; then
            log_info "Stopping here. Test your package and run this script again for production upload."
            exit 0
        fi
    fi
}

# Upload to PyPI
upload_pypi() {
    log_warning "Ready to upload to PyPI. This action cannot be undone!"
    log_warning "Version: $(grep version pyproject.toml | head -1 | cut -d'"' -f2)"
    echo ""
    echo "Please ensure:"
    echo "  1. You have a PyPI account"
    echo "  2. You have configured your PyPI API token (~/.pypirc or environment variable)"
    echo "  3. The version number is correct"
    echo "  4. You have tested the package"
    echo ""
    log_warning "Continue with upload to PyPI? (yes/no - must type 'yes' to confirm)"
    read -r response

    if [ "$response" = "yes" ]; then
        log_info "Uploading to PyPI..."
        twine upload dist/*

        echo ""
        echo "=========================================="
        log_info "🎉 SUCCESS! Package uploaded to PyPI!"
        echo "=========================================="
        echo ""
        log_info "Users can now install with:"
        echo "  pip install multicord"
        echo ""
        log_info "View your package at:"
        echo "  https://pypi.org/project/multicord/"
        echo ""
    else
        log_info "Upload cancelled"
        exit 0
    fi
}

# Post-upload steps
post_upload() {
    log_info "Post-upload recommendations:"
    echo ""
    echo "1. Create a GitHub release with the same version number"
    echo "2. Update the documentation at docs.multicord.io"
    echo "3. Announce the release on:"
    echo "   - Reddit (r/discordapp, r/Discord_Bots)"
    echo "   - Discord developer communities"
    echo "   - Twitter/X with #discord #python hashtags"
    echo "4. Monitor for issues at: https://github.com/HollowTheSilver/MultiCord/issues"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "MultiCord CLI - PyPI Publishing Script"
    echo "=========================================="
    echo ""

    check_prerequisites
    clean_build
    run_tests
    build_package
    check_package
    upload_test_pypi
    upload_pypi
    post_upload
}

# Run if not sourced
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi