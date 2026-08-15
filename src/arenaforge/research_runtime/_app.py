"""Single-source-of-truth for the ArenaForge product identity."""

from pathlib import Path

APP_NAME = "arenaforge"

CLI_COMMAND = APP_NAME

# Product taglines, shown on the splash banner and in `--help`.
TAGLINE = "Run research with evidence."
TAGLINE_SUB = "Every hypothesis becomes an isolated experiment with a recorded decision."

CONFIG_DIR_NAME = f".{APP_NAME}"
CONFIG_FILE_NAME = f"{APP_NAME}.yaml"

GLOBAL_CONFIG_DIR = Path.home() / f".{APP_NAME}"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

# Legacy paths kept for one release so users with a pre-rename config
# don't lose their settings. The user_config loader falls back to these.
LEGACY_GLOBAL_CONFIG_DIR = Path.home() / ".autoresearch"
LEGACY_GLOBAL_CONFIG_FILE = LEGACY_GLOBAL_CONFIG_DIR / "config.yaml"
