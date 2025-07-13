"""CLI entry point wrapper for the ``csvxlm`` console script."""

from main import main as _main


def main() -> None:
    """Run the application's main CLI."""
    _main()

