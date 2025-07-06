from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Union

DEFAULT_CONFIG_PATH = Path("config_rules/config.json")


def load_config(
    config_path: Union[str, os.PathLike[str], Path] = DEFAULT_CONFIG_PATH,
) -> dict:
    """
    Loads the JSON configuration file.

    Args:
        config_path (str): The path to the configuration file.

    Returns:
        dict: The loaded configuration as a dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError:
            If the config file is not valid JSON or the top-level value is not
            a dict.
        Exception: For other unexpected errors during file loading.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        # Try to construct path relative to this file's directory if a
        # relative path is given
        if not config_path.is_absolute():
            current_dir = Path(__file__).resolve().parent
            rel_path = current_dir / ".." / ".." / ".." / config_path
            if rel_path.exists():
                config_path = rel_path
            else:
                raise FileNotFoundError(
                    "Configuration file not found at"
                    f" {config_path} or {rel_path}"
                )
        else:
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}"
            )

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Error decoding JSON from config file {config_path}: {e}"
        )
    except Exception as e:
        # Catch any other exception during file reading (e.g.,
        # permission issues)
        raise Exception(
            "An unexpected error occurred while loading config "
            f"{config_path}: {e}"
        )

    if not isinstance(config, dict):
        raise ValueError(
            "Configuration content must be a JSON object (dictionary), but got"
            f" {type(config)} from {config_path}"
        )

    return config
