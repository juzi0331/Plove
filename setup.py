from setuptools import setup, find_packages
setup(
    name="crawler_kit",
    version="1.0.0",
    packages=find_packages(where="crawler"),
    package_dir={"": "crawler"},
    package_data={"crawler_kit": ["*.py"]},
)
