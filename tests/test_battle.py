"""Integration tests for battle.py entry point."""
from __future__ import annotations

import os
import json
import pytest
from unittest.mock import patch

from battle import parse_args, run_battle, print_summary
from scraper import SEED_BUGS
from models import MockModel
from evaluator import evaluate


# ── parse_args ────────────────────────────────────────────────────────────────

class TestParseArgs:
    def test_default_count(self):
        args = parse_args([])
        assert args.count > 0

    def test_count_override(self):
        args = parse_args(["--count", "10"])
        assert args.count == 10

    def test_mock_flag(self):
        args = parse_args(["--mock"])
        assert args.mock is True

    def test_no_html_flag(self):
        args = parse_args(["--no-html"])
        assert args.no_html is True

    def test_workers_flag(self):
        args = parse_args(["--workers", "4"])
        assert args.workers == 4


# ── run_battle ────────────────────────────────────────────────────────────────

class TestRunBattle:
    def test_returns_results_for_each_bug(self):
        bugs = SEED_BUGS[:3]
        nem = MockModel("Nemotron")
        gpt = MockModel("GPT-Nano")
        results = run_battle(bugs, nem, gpt, workers=1)
        assert len(results) == len(bugs)

    def test_results_have_winner(self):
        bugs = SEED_BUGS[:2]
        nem = MockModel("Nemotron")
        gpt = MockModel("GPT-Nano")
        results = run_battle(bugs, nem, gpt)
        for r in results:
            assert r.winner in ("nemotron", "gpt", "tie")

    def test_all_bugs_processed(self):
        bugs = SEED_BUGS[:5]
        nem = MockModel("Nemotron")
        gpt = MockModel("GPT-Nano")
        results = run_battle(bugs, nem, gpt)
        assert len(results) == 5


# ── main (via battle.main) ────────────────────────────────────────────────────

class TestMain:
    def test_main_mock_mode(self, tmp_path):
        from battle import main
        args = [
            "--count", "3",
            "--mock",
            "--output-dir", str(tmp_path),
        ]
        with patch("scraper._search_forum", return_value=[]):
            exit_code = main(args)
        assert exit_code == 0

    def test_main_creates_html(self, tmp_path):
        from battle import main
        args = [
            "--count", "2",
            "--mock",
            "--output-dir", str(tmp_path),
        ]
        with patch("scraper._search_forum", return_value=[]):
            main(args)
        html_files = list(tmp_path.glob("*.html"))
        assert len(html_files) == 1

    def test_main_creates_json(self, tmp_path):
        from battle import main
        args = [
            "--count", "2",
            "--mock",
            "--output-dir", str(tmp_path),
        ]
        with patch("scraper._search_forum", return_value=[]):
            main(args)
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text())
        assert len(data) == 2

    def test_main_no_html_flag(self, tmp_path):
        from battle import main
        args = [
            "--count", "2",
            "--mock",
            "--no-html",
            "--output-dir", str(tmp_path),
        ]
        with patch("scraper._search_forum", return_value=[]):
            main(args)
        html_files = list(tmp_path.glob("*.html"))
        assert len(html_files) == 0
