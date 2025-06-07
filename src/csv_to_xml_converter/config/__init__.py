import json
import os

DEFAULT_CONFIG_PATH = "config_rules/config.json"

def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Loads the JSON configuration file.

    Args:
        config_path (str): The path to the configuration file.

    Returns:
        dict: The loaded configuration as a dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file is not valid JSON or top-level is not a dict.
        Exception: For other unexpected errors during file loading.
    """
    if not os.path.exists(config_path):
        # Try to construct path relative to this file's directory if a relative path is given
        # This helps when the script is run from different working directories.
        if not os.path.isabs(config_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            rel_path = os.path.join(current_dir, "..", "..", "..", config_path) # Adjust based on actual structure if needed
            if os.path.exists(rel_path):
                config_path = rel_path
            else:
                 raise FileNotFoundError(f"Configuration file not found at {config_path} or {rel_path}")
        else:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f: # Specify encoding
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from config file {config_path}: {e}")
    except Exception as e:
        # Catch any other exception during file reading (e.g., permission issues)
        raise Exception(f"An unexpected error occurred while loading config {config_path}: {e}")

    if not isinstance(config, dict):
        raise ValueError(f"Configuration content must be a JSON object (dictionary), but got {type(config)} from {config_path}")

    return config


