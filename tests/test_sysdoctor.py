"""Tests for sysdoctor — pure functions and cross-platform behavior."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sysdoctor.sysdoctor import human_size, human_duration, cmd_path


class TestHumanSize:
    def test_bytes(self):
        assert human_size(500) == "500 B"

    def test_kib(self):
        assert human_size(1024) == "1.0 KiB"

    def test_mib(self):
        assert human_size(1_048_576) == "1.0 MiB"

    def test_gib(self):
        assert human_size(1_073_741_824) == "1.0 GiB"

    def test_zero(self):
        assert human_size(0) == "0 B"

    def test_negative(self):
        result = human_size(-100)
        assert "100" in result


class TestHumanDuration:
    def test_zero(self):
        assert human_duration(0) == "0d 0h 0m"

    def test_seconds(self):
        assert human_duration(30) == "0d 0h 0m"

    def test_minutes(self):
        assert human_duration(120) == "0d 0h 2m"

    def test_hours(self):
        assert human_duration(7200) == "0d 2h 0m"

    def test_days(self):
        assert human_duration(90000) == "1d 1h 0m"


class TestCmdPath:
    def test_no_problems(self, monkeypatch, tmp_path):
        sep = os.pathsep
        d1, d2 = str(tmp_path / "a"), str(tmp_path / "b")
        Path(d1).mkdir(); Path(d2).mkdir()
        monkeypatch.setenv("PATH", d1 + sep + d2)
        result = cmd_path(argparse.Namespace())
        assert result == 0

    def test_duplicate_detected(self, monkeypatch, tmp_path):
        sep = os.pathsep
        d = str(tmp_path / "dup")
        Path(d).mkdir()
        monkeypatch.setenv("PATH", d + sep + d)
        result = cmd_path(argparse.Namespace())
        assert result == 1

    def test_missing_entry_detected(self, monkeypatch, tmp_path):
        sep = os.pathsep
        monkeypatch.setenv("PATH", str(tmp_path / "nope") + sep + str(tmp_path))
        result = cmd_path(argparse.Namespace())
        assert result == 1


class TestParser:
    def test_prog_name(self):
        from sysdoctor.sysdoctor import build_parser
        parser = build_parser()
        assert parser.prog == "sysdoctor"

    def test_subcommands(self):
        from sysdoctor.sysdoctor import build_parser
        parser = build_parser()
        # Subcommands that take no required positional args
        for cmd in ("info", "disk", "net", "path", "clean"):
            args = parser.parse_args([cmd])
            assert hasattr(args, "func"), f"subcommand {cmd} missing func"
        # 'big' requires a path argument
        args = parser.parse_args(["big", "."])
        assert hasattr(args, "func")
        assert args.path == "."
