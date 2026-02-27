"""
Setup script for Bitcoin Terminal
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme = Path(__file__).parent / "README.md"
long_description = readme.read_text() if readme.exists() else ""

# Read requirements (skip comments and blank lines)
requirements = Path(__file__).parent / "requirements.txt"
install_requires = []
if requirements.exists():
    install_requires = [
        line.strip() for line in requirements.read_text().splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]

setup(
    name="bitcoin-terminal",
    version="0.1.0",
    author="Bitcoin Terminal Contributors",
    description="A beautiful TUI for Bitcoin Node monitoring",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/bitcoin-terminal",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: User Interfaces",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "bitcoin-terminal=bitcoin_terminal.__main__:main",
        ],
    },
    keywords="bitcoin node terminal tui dashboard monitoring",
)
