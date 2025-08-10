#!/usr/bin/env python3

import os

from setuptools import setup, find_packages

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read requirements
with open(os.path.join(this_directory, 'requirements.txt'), encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]


# Get version and constants directly
def get_package_info():
    version_file = os.path.join(this_directory, 'featureflagshq', '__init__.py')
    version = None
    company_name = None

    with open(version_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                version = line.split('=')[1].strip().strip('"\'')
            elif line.startswith('COMPANY_NAME'):
                company_name = line.split('=')[1].strip().strip('"\'')

    return version, company_name


version, company_name = get_package_info()

setup(
    name="featureflagshq",
    version=version,
    author=company_name,
    author_email="hello@featureflagshq.com",
    description=f"A secure, high-performance Python SDK for {company_name} feature flag management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/featureflagshq/python-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/featureflagshq/python-sdk/issues",
        "Documentation": "https://featureflagshq.com/documentation/",
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
