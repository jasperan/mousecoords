"""Tests for the system diagnostics module."""

import pytest
from unittest.mock import patch

from mousecoords.doctor import (
    CheckResult, collect_diagnostics, print_diagnostics,
    check_display, check_pyautogui, check_opencv, check_rich,
    check_tkinter, check_pynput, check_keyboard,
)


class TestCheckResult:
    def test_structure(self):
        r = CheckResult("test", True, "all good")
        assert r.name == "test"
        assert r.passed is True
        assert r.detail == "all good"
        assert r.required is True

    def test_optional(self):
        r = CheckResult("opt", False, "missing", required=False)
        assert r.required is False


class TestIndividualChecks:
    def test_check_pyautogui(self):
        result = check_pyautogui()
        assert result.name == "pyautogui"
        assert result.passed is True  # it's a core dep, should be installed

    def test_check_keyboard(self):
        result = check_keyboard()
        assert result.name == "keyboard"
        # keyboard is a core dep
        assert result.passed is True

    def test_check_opencv(self):
        result = check_opencv()
        assert result.name == "opencv"
        assert isinstance(result.passed, bool)
        assert result.required is False

    def test_check_rich(self):
        result = check_rich()
        assert result.name == "rich"
        assert isinstance(result.passed, bool)
        assert result.required is False

    def test_check_tkinter(self):
        result = check_tkinter()
        assert result.name == "tkinter"
        assert isinstance(result.passed, bool)

    def test_check_pynput(self):
        result = check_pynput()
        assert result.name == "pynput"
        assert isinstance(result.passed, bool)


class TestCollectDiagnostics:
    def test_returns_list(self):
        results = collect_diagnostics()
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, CheckResult) for r in results)

    def test_custom_checks(self):
        def always_pass():
            return CheckResult("custom", True, "ok")
        results = collect_diagnostics([always_pass])
        assert len(results) == 1
        assert results[0].passed is True

    def test_handles_check_exception(self):
        def bad_check():
            raise RuntimeError("boom")
        results = collect_diagnostics([bad_check])
        assert len(results) == 1
        assert results[0].passed is False
        assert "unexpected error" in results[0].detail


class TestPrintDiagnostics:
    def test_prints_output(self, capsys):
        results = [
            CheckResult("foo", True, "ok"),
            CheckResult("bar", False, "missing", required=False),
        ]
        print_diagnostics(results)
        captured = capsys.readouterr()
        assert "foo" in captured.out
        assert "PASS" in captured.out
        assert "bar" in captured.out
        assert "FAIL" in captured.out
        assert "1/2" in captured.out
