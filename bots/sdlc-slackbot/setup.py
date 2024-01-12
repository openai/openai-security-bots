from setuptools import setup, find_packages

with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

setup(
    name="sdlc_bot",
    version="0.1",
    packages=find_packages(),
    install_requires=requirements,
)
