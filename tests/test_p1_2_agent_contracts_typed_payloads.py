import sys
from collections.abc import Mapping
from pathlib import Path
from typing import get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime import agent_contracts  # noqa: E402


def _assert_payload_mapping(annotation):
    assert get_origin(annotation) is Mapping
    key_type, value_type = get_args(annotation)
    assert key_type is str
    value_args = set(get_args(value_type))
    assert {str, int, float, bool, type(None)} <= value_args
    assert any(get_origin(arg) is tuple for arg in value_args)
    assert any(get_origin(arg) is Mapping for arg in value_args)


def test_agent_contract_payloads_use_json_like_types():
    request_hints = get_type_hints(agent_contracts.AgentRequest)
    call_hints = get_type_hints(agent_contracts.ToolCall)
    result_hints = get_type_hints(agent_contracts.ToolResult)

    assert agent_contracts.JsonScalar == str | int | float | bool | None
    json_value_args = set(get_args(agent_contracts.JsonValue))
    assert {str, int, float, bool, type(None)} <= json_value_args
    assert any(get_origin(arg) is tuple for arg in json_value_args)
    assert any(get_origin(arg) is Mapping for arg in json_value_args)
    _assert_payload_mapping(request_hints["context"])
    _assert_payload_mapping(call_hints["arguments"])
    _assert_payload_mapping(result_hints["metadata"])
