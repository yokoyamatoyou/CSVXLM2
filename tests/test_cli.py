import sys
from pathlib import Path

# Allow importing main from src directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from main import parse_args


def test_parse_args_log_level():
    args = parse_args(["--log-level", "DEBUG"])
    assert args.log_level == "DEBUG"

def test_parse_args_log_level_default():
    args = parse_args([])
    assert args.log_level is None

