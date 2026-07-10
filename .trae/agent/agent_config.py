import json
import shlex
from pathlib import Path


def load_agent_config(config_path):
    config_path = Path(config_path)
    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def normalize_configured_command(command):
    if isinstance(command, list):
        return [str(part) for part in command]
    if isinstance(command, str):
        return shlex.split(command)
    raise ValueError("命令必须是字符串或字符串数组")
