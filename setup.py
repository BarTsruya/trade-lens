from setuptools import setup, find_packages


setup(
    name="TradeLens",
    version="0.1.0",
    description="A small library for processing TradeLens account data",
    author="",
    author_email="",
    packages=find_packages(include=["trade_lens", "trade_lens.*"]),
    install_requires=[
        "pandas>=1.0",
        "pydantic>=2.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    zip_safe=False,
)
