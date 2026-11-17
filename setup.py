from setuptools import setup, find_packages
from pathlib import Path
import re

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ""
# Resolve repository-relative Markdown links for PyPI's rendered project page.
long_description = re.sub(
    r"\]\((?!https?://|#)([^)]+)\)",
    lambda match: "](https://github.com/Jshulgach/aruco-pose/blob/main/" + match.group(1) + ")",
    long_description,
)

setup(
    name="aruco-pose",
    version="0.3.0",
    license_expression="Apache-2.0",
    license_files=["LICENSE"],
    author="Jonathan Shulgach",
    author_email="jshulgac@andrew.cmu.edu",
    description="Print, calibrate and track rigid ArUco targets with a shared pose API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Jshulgach/aruco-pose",
    packages=find_packages(include=["aruco_pose", "aruco_pose.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Image Recognition",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.24,<3",
        "opencv-contrib-python>=4.8,<5",
        "pyyaml>=5.4",
        "packaging>=20.0",
        "click>=8.0",
        "scipy>=1.7.0",
    ],
    extras_require={
        'dev': [
            'pytest>=6.0',
            'matplotlib>=3.5',
            'pytest-cov>=2.0',
            'black>=21.0',
            'flake8>=3.9',
            'mypy>=0.910',
        ],
        'docs': [
            'sphinx>=4.0',
            'sphinx-rtd-theme>=0.5',
        ],
    },
    entry_points={
        'console_scripts': [
            'aruco-pose=aruco_pose.cli:cli',
            'aruco-cli=aruco_pose.cli:cli',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.yaml', '*.json'],
    },
    keywords='aruco markers computer-vision pose-estimation opencv tracking',
    project_urls={
        'Bug Reports': 'https://github.com/Jshulgach/aruco-pose/issues',
        'Source': 'https://github.com/Jshulgach/aruco-pose',
    },
)
