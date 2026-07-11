import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SCRIPT = ROOT / "scripts" / "p0_1_synthpilot_mcp_evidence.py"


def _load_evidence_module():
    spec = importlib.util.spec_from_file_location(
        "p0_1_synthpilot_mcp_evidence",
        EVIDENCE_SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_p0_1_synthpilot_evidence_selects_safe_zero_argument_tool():
    module = _load_evidence_module()

    selected = module._choose_safe_tool(
        [
            {
                "name": "delete_project",
                "inputSchema": {"type": "object"},
            },
            {
                "name": "version",
                "inputSchema": {"type": "object"},
            },
            {
                "name": "diagnostic_status",
                "inputSchema": {"type": "object"},
            },
        ]
    )

    assert selected["name"] == "diagnostic_status"


def test_p0_1_synthpilot_evidence_rejects_required_argument_tools():
    module = _load_evidence_module()

    selected = module._choose_safe_tool(
        [
            {
                "name": "version",
                "inputSchema": {
                    "type": "object",
                    "required": ["project"],
                    "properties": {"project": {"type": "string"}},
                },
            },
            {
                "name": "echo",
                "input_schema": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {"text": {"type": "string"}},
                },
            },
        ]
    )

    assert selected is None


def test_p0_1_synthpilot_evidence_blocks_ambiguous_no_argument_tools():
    module = _load_evidence_module()

    selected = module._choose_safe_tool(
        [
            {
                "name": "create_project",
                "inputSchema": {"type": "object"},
            },
            {
                "name": "download_bitstream",
                "inputSchema": {"type": "object"},
            },
        ]
    )

    assert selected is None


def test_p0_1_synthpilot_evidence_allows_single_no_argument_fallback():
    module = _load_evidence_module()

    selected = module._choose_safe_tool(
        [
            {
                "name": "status",
                "inputSchema": {"type": "object"},
            }
        ]
    )

    assert selected["name"] == "status"
