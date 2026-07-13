import json
import sys
from typing import Any, TextIO


def build_agent_composition_error_lines(prefix: str, exc: BaseException) -> list[str]:
    return ["{}: {}".format(prefix, exc)]


def emit_agent_composition_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)


def build_agent(agent_type: Any) -> Any:
    try:
        return agent_type()
    except FileNotFoundError as exc:
        emit_agent_composition_lines(
            build_agent_composition_error_lines("配置文件缺失", exc),
            stream=sys.stderr,
        )
        return None
    except json.JSONDecodeError as exc:
        emit_agent_composition_lines(
            build_agent_composition_error_lines("配置文件不是合法 JSON", exc),
            stream=sys.stderr,
        )
        return None
    except KeyError as exc:
        emit_agent_composition_lines(
            build_agent_composition_error_lines("配置文件缺少必要字段", exc),
            stream=sys.stderr,
        )
        return None
    except ValueError as exc:
        emit_agent_composition_lines(
            build_agent_composition_error_lines("配置无效", exc),
            stream=sys.stderr,
        )
        return None
