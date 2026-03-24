# Nemotron Cascade 2-30B vs GPT-4.1-nano – Head-to-head code generation benchmark

> *Made autonomously using [NEO](https://heyneo.so) · [![Install NEO Extension](https://img.shields.io/badge/VS%20Code-Install%20NEO-7B61FF?logo=visual-studio-code)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)*

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-105%20passed-brightgreen.svg)]()

> Benchmark Nemotron Cascade 2-30B and GPT-4.1-nano on real-world code generation tasks to see which model performs better under practical conditions.

## Install

```bash
git clone https://github.com/dakshjain-1616/nemotron-cascade-2-30b-vs-gpt
cd nemotron-cascade-2-30b-vs-gpt
pip install -r requirements.txt
```

## Quickstart

```bash
python scripts/demo.py
# Outputs a detailed HTML report with side-by-side comparisons
```

## Key features

- Real-world code generation tasks scraped from forums and open-source projects  
- Evaluates models on compilability, correctness, and verbosity  
- Generates an interactive HTML leaderboard with side-by-side diffs  

## Run tests

```bash
pytest tests/ -q
# 105 passed
```

## Project structure

```
nemotron-cascade-2-30b-vs-gpt/
├── battle.py          ← main benchmarking logic  
├── config.py          ← API keys and settings  
├── evaluator.py       ← scoring metrics  
├── models.py          ← LLM wrappers  
├── reporter.py        ← report generation  
├── scraper.py         ← scraping real-world tasks  
├── scripts/  
│   └── demo.py        ← demo script  
└── tests/             ← test suite  
```