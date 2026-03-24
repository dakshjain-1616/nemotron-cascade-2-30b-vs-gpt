from setuptools import setup, find_packages

setup(
    name="nemotron-bench",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "openai>=1.30.0",
        "python-dotenv>=1.0.0",
        "rich>=13.7.0",
        "lxml>=5.2.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "nemotron-bench=nemotron_bench.battle:main",
        ],
    },
)
