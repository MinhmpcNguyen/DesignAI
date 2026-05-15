import logging
import os
from typing import cast

import yaml
from dotenv import load_dotenv

from config.models import RootConfig

_ = load_dotenv()

APP_CONFIG_FILE = "app-config.yaml"


logger = logging.getLogger(__name__)


def load_config(app_config_path: str) -> RootConfig:
    """
    Load the application configuration from YAML with environment expansion.

    Args:
        config_path (str): Path to the YAML configuration file.

    Returns:
        The validated root configuration model.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If there's an issue parsing the YAML file.
        Exception: For any other unforeseen errors.
    """
    try:
        # Resolve absolute path of the config file
        full_path_app_config = os.path.abspath(app_config_path)

        if not os.path.exists(full_path_app_config):
            raise FileNotFoundError(
                f"Application configuration file not found: {full_path_app_config}"
            )

        with open(full_path_app_config, encoding="utf-8") as f:
            raw_content = f.read()

        # Expand environment variables and load YAML content
        expanded_content = os.path.expandvars(raw_content)
        # PyYAML returns untyped data; RootConfig validation below cleans the boundary.
        config_payload = cast(object, yaml.safe_load(expanded_content))
        if not isinstance(config_payload, dict):
            raise ValueError("Application configuration root must be a mapping.")

        validated_config = RootConfig.model_validate(config_payload)
        logger.info(
            "Configuration loaded and validated successfully: %s", full_path_app_config
        )

        logger.info("Configuration loaded and validated successfully.")
        return validated_config

    except FileNotFoundError as e:
        logger.error("Configuration file not found: %s", e)
        raise
    except yaml.YAMLError as e:
        logger.error("Error parsing YAML configuration: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error loading configuration: %s", e)
        raise


# Determine the path to the configuration file
config_file = os.path.join(os.path.dirname(__file__), os.pardir, APP_CONFIG_FILE)

# Load the application configuration
try:
    root_config: RootConfig = load_config(app_config_path=config_file)
    logger.info("Application configuration loaded from %s", config_file)
except Exception as e:
    logger.critical("Failed to load application configuration: %s", e)
    raise e
