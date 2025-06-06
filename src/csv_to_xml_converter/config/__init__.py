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

if __name__ == '__main__':
    # Example of how to test the config loading
    # This part will only run when the script is executed directly (e.g., python -m csv_to_xml_converter.config)
    print("Attempting to load default configuration...")
    try:
        cfg = load_config()
        print("Default configuration loaded successfully:")
        # print(json.dumps(cfg, indent=2)) # Pretty print the config

        # Example: Accessing a specific configuration value
        log_level = cfg.get("logging", {}).get("log_level", "NOT_FOUND")
        print(f"Log level from config: {log_level}")

        # Test with a non-existent file
        # print("\nAttempting to load a non-existent configuration file...")
        # try:
        #     load_config("non_existent_config.json")
        # except FileNotFoundError as e:
        #     print(f"Caught expected error: {e}")
        # except Exception as e:
        #     print(f"Caught unexpected error: {e}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure 'config_rules/config.json' exists in the project root or provide a valid path.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    # To run this test:
    # 1. Make sure you are in the root directory of the project (e.g., /app)
    # 2. Run: python -m src.csv_to_xml_converter.config
    #    (Adjust the module path if your project structure or PYTHONPATH is different)
    #    Alternatively, if your top-level 'src' is in PYTHONPATH:
    #    python -m csv_to_xml_converter.config
