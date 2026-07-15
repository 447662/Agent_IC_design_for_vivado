# P0-1 SynthPilot Follow-up

## Current Status

As of 2026-07-13, P0-2 through P2 have completed their currently active scope
without claiming SynthPilot real MCP completion. The real SynthPilot handshake
is the only remaining active P0-1 blocker; the separately user-paused P1-2 and
P1-3 broad acceptance items remain classified as unfinished work.

The repository has a real MCP evidence runner at
`scripts/p0_1_synthpilot_mcp_evidence.py`, but the real SynthPilot process exits
before MCP `initialize`.

## Blocking Issue

The SynthPilot license is configured on this machine, but license verification
currently fails with a device-limit error:

```text
Device limit reached (1). Run `synthpilot deactivate` on an old device to free a slot,
or contact support.
```

The license key itself is intentionally not recorded in repository evidence.

The current evidence file is:

```text
docs/testing/evidence/synthpilot_tools_list.json
```

## Resume Criteria

P0-1 can resume after the license slot is freed or support resets the activation.
No further retries should be made before that external state changes. When
unblocked, rerun:

```powershell
uv run --offline --frozen python scripts/p0_1_synthpilot_mcp_evidence.py
```

Expected follow-up evidence:

- MCP `initialize` succeeds.
- `tools/list` returns real SynthPilot tool schemas.
- The evidence runner selects only a clearly safe zero-required-argument tool.
- One safe real `tools/call` succeeds or fails with a tool-level diagnostic rather
  than a process-start/license failure.
