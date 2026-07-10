from typing import Any
import json
import sys


def build_agent(agent_type: Any) -> Any:
    try:
        return agent_type()
    except FileNotFoundError as exc:
        print("配置文件缺失: {}".format(exc), file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print("配置文件不是合法 JSON: {}".format(exc), file=sys.stderr)
        return None
    except KeyError as exc:
        print("配置文件缺少必要字段: {}".format(exc), file=sys.stderr)
        return None
    except ValueError as exc:
        print("配置无效: {}".format(exc), file=sys.stderr)
        return None
