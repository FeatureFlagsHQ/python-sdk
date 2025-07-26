#!/usr/bin/env python3
"""
Fallback setup.py for compatibility with older pip versions.
Modern packaging uses pyproject.toml, but this ensures compatibility.
"""

from setuptools import setup, find_packages


# Read version from _version.py
def get_version():
    """Get version from _version.py file"""
    version_dict = {}
    with open("src/featureflagshq/_version.py") as f:
        exec(f.read(), version_dict)
    return version_dict["__version__"]


# Read long description from README
def get_long_description():
    """Get long description from README.md"""
    try:
        with open("README.md", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Official Python SDK for FeatureFlagsHQ - Enterprise feature flag management"


# Read requirements from requirements.txt
def get_requirements():
    """Get requirements from requirements.txt"""
    try:
        with open("requirements.txt", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return [
            "requests>=2.28.0,<3.0.0",
            "psutil>=5.9.0",
        ]


if __name__ == "__main__":
    setup(
        name="featureflagshq",
        version=get_version(),
        description="Official Python SDK for FeatureFlagsHQ - Enterprise feature flag management",
        long_description=get_long_description(),
        long_description_content_type="text/markdown",
        author="FeatureFlagsHQ Team",
        author_email="hello@featureflagshq.com",
        url="https://featureflagshq.com",
        project_urls={
            "Homepage": "https://featureflagshq.com",
            "Documentation": "https://github.com/featureflagshq/python-sdk",
            "Repository": "https://github.com/featureflagshq/python-sdk",
            "Changelog": "https://github.com/featureflagshq/python-sdk/blob/main/CHANGELOG.md",
            "Bug Reports": "https://github.com/featureflagshq/python-sdk/issues",
            "Security Policy": "https://github.com/featureflagshq/python-sdk/security/policy",
        },

        # Package discovery
        package_dir={"": "src"},
        packages=find_packages(where="src"),
        include_package_data=True,

        # Python version requirements
        python_requires=">=3.8",

        # Dependencies
        install_requires=get_requirements(),

        # Optional dependencies
        extras_require={
            "dev": [
                "pytest>=7.0.0",
                "pytest-cov>=4.0.0",
                "pytest-mock>=3.10.0",
                "pytest-asyncio>=0.21.0",
                "black>=23.0.0",
                "isort>=5.12.0",
                "flake8>=6.0.0",
                "mypy>=1.0.0",
                "pre-commit>=3.0.0",
                "twine>=4.0.0",
                "build>=0.10.0",
            ],
            "test": [
                "pytest>=7.0.0",
                "pytest-cov>=4.0.0",
                "pytest-mock>=3.10.0",
                "pytest-asyncio>=0.21.0",
                "responses>=0.23.0",
                "freezegun>=1.2.0",
            ],
            "docs": [
                "sphinx>=6.0.0",
                "sphinx-rtd-theme>=1.2.0",
                "sphinx-autodoc-typehints>=1.20.0",
                "myst-parser>=1.0.0",
            ],
            "security": [
                "bandit>=1.7.0",
                "safety>=2.3.0",
            ],
        },

        # Package metadata
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: System :: Monitoring",
            "Typing :: Typed",
        ],

        # Keywords for PyPI search
        keywords=[
            "feature-flags",
            "feature-toggles",
            "a/b-testing",
            "experimentation",
            "rollouts",
            "segments",
            "enterprise",
            "sdk",
            "featureflagshq"
        ],

        # License
        license="MIT",

        # Package data
        package_data={
            "featureflagshq": ["py.typed"],
        },

        # Entry points (if you want CLI commands)
        entry_points={
            "console_scripts": [
                # Uncomment if you want to add CLI commands
                # "featureflagshq=featureflagshq.cli:main",
            ],
        },

        # Zip safety
        zip_safe=False,
    )
