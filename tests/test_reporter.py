"""Tests for the reporter module."""
from __future__ import annotations

import os
import json
import tempfile

import pytest

from scraper import SEED_BUGS
from models import MockModel
from evaluator import evaluate, EvalResult
from reporter import generate_report, save_json, _render_diff, _pct


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_results(n: int = 3) -> list[EvalResult]:
    nem = MockModel("Nemotron")
    gpt = MockModel("GPT-Nano")
    results = []
    for bug in SEED_BUGS[:n]:
        nem_r = nem.fix_bug(bug)
        gpt_r = gpt.fix_bug(bug)
        results.append(evaluate(bug, nem_r, gpt_r))
    return results


# ── generate_report ───────────────────────────────────────────────────────────

class TestGenerateReport:
    def test_creates_file(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "report.html")
        out = generate_report(results, path)
        assert os.path.exists(out)

    def test_returns_path(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "report.html")
        out = generate_report(results, path)
        assert out == path

    def test_html_structure(self, tmp_path):
        results = make_results(3)
        path = str(tmp_path / "report.html")
        generate_report(results, path)
        content = open(path, encoding="utf-8").read()
        assert "<!DOCTYPE html>" in content
        assert "Arduino AI Battle" in content
        assert "Nemotron" in content
        assert "GPT-Nano" in content

    def test_bug_count_in_report(self, tmp_path):
        results = make_results(3)
        path = str(tmp_path / "report.html")
        generate_report(results, path)
        content = open(path, encoding="utf-8").read()
        assert "3 bugs" in content

    def test_winner_badges_present(self, tmp_path):
        results = make_results(3)
        path = str(tmp_path / "report.html")
        generate_report(results, path)
        content = open(path, encoding="utf-8").read()
        assert "winner-" in content  # CSS class prefix

    def test_neo_attribution_in_footer(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "report.html")
        generate_report(results, path)
        content = open(path, encoding="utf-8").read()
        assert "heyneo.so" in content
        assert "NEO" in content

    def test_empty_results_raises(self):
        with pytest.raises(ValueError):
            generate_report([], "/tmp/test.html")

    def test_score_percentages_present(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "report.html")
        generate_report(results, path)
        content = open(path, encoding="utf-8").read()
        # Should have percentage values
        assert "%" in content

    def test_diff_section_present(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "report.html")
        generate_report(results, path)
        content = open(path, encoding="utf-8").read()
        assert "diff" in content.lower()


# ── save_json ─────────────────────────────────────────────────────────────────

class TestSaveJson:
    def test_creates_file(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "results.json")
        out = save_json(results, path)
        assert os.path.exists(out)

    def test_valid_json(self, tmp_path):
        results = make_results(2)
        path = str(tmp_path / "results.json")
        save_json(results, path)
        data = json.loads(open(path).read())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_json_structure(self, tmp_path):
        results = make_results(1)
        path = str(tmp_path / "results.json")
        save_json(results, path)
        data = json.loads(open(path).read())
        item = data[0]
        assert "title" in item
        assert "nemotron" in item
        assert "gpt" in item
        assert "winner" in item
        assert "compilable" in item["nemotron"]
        assert "total" in item["gpt"]


# ── Helper functions ──────────────────────────────────────────────────────────

class TestHelpers:
    def test_pct_formatting(self):
        assert _pct(1.0) == "100%"
        assert _pct(0.0) == "0%"
        assert _pct(0.756) == "76%"

    def test_render_diff_same_text(self):
        html = _render_diff("hello world", "hello world")
        assert "identical" in html.lower()

    def test_render_diff_different_text(self):
        html = _render_diff("line one\nline two", "line one\nline three")
        assert "diff-" in html  # CSS classes present

    def test_render_diff_returns_string(self):
        result = _render_diff("a", "b")
        assert isinstance(result, str)
