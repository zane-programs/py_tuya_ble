"""Setup script for py_tuya_ble package."""

from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read version from package
with open("py_tuya_ble/__init__.py", "r") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split('"')[1]
            break

setup(
    name="py_tuya_ble",
    version=version,
    author="Your Name",
    author_email="your.email@example.com",
    description="A standalone Python library for Tuya BLE devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/py_tuya_ble",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "bleak>=0.21.0",
        "pycryptodome>=3.15.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/yourusername/py_tuya_ble/issues",
        "Source": "https://github.com/yourusername/py_tuya_ble",
    },
)