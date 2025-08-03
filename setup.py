#!/usr/bin/env python3

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read requirements
with open(os.path.join(this_directory, 'requirements.txt'), encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="featureflagshq-sdk",
    version="1.0.0",
    author="FeatureFlagsHQ",
    author_email="hello@featureflagshq.com",
    description="A secure, high-performance Python SDK for FeatureFlagsHQ feature flag management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/featureflagshq/python-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/featureflagshq/python-sdk/issues",
        "Documentation": "https://docs.featureflagshq.com",
        "Homepage": "https://featureflagshq.com",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.812",
            "responses>=0.18.0",
            "twine>=3.0",
            "build>=0.7.0",
        ],
    },
    keywords="feature flags, feature toggles, experimentation, a/b testing, configuration management",
    include_package_data=True,
    zip_safe=False,
)