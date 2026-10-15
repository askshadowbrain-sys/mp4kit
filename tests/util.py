"""Shared helpers for the per-episode tests."""
import contextlib
import io
from pathlib import Path

from mp4kit import cli

TESTFILES = Path(__file__).parents[1] / "testfiles" / "out"


def data(name) -> bytes:
    """Bytes of a committed test file."""
    return (TESTFILES / name).read_bytes()


def run_cli(*argv) -> str:
    """Run mp4kit.cli.main(argv) and return what it printed to stdout."""
    return run_cli_code(*argv)[1]


def run_cli_code(*argv) -> tuple:
    """Run mp4kit.cli.main(argv) and return (exit code, what it printed to stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(list(argv))
    return code, buf.getvalue()
