import pkg_resources
from setuptools import setup, find_packages

with open("requirements.txt") as requirements_file:
    requirements = requirements_file.readlines()

setup(
    name="runner",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        str(requirement) for requirement in pkg_resources.parse_requirements(requirements)
    ],
    entry_points={
        "console_scripts": [
            "runner = runner.main:main",
        ],
    },
    python_requires=">=3.6",
) 