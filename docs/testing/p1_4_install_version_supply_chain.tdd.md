# P1-4 Install, Version, and Supply Chain Reproducibility TDD Evidence

## Source Plan

Derived from the active P1-4 objective:

- Add a build backend, package discovery, and `digital-ic-agent` console entrypoint.
- Use one version source.
- Resolve Vivado from configuration, environment variables, and discovery instead
  of machine-specific default paths.
- Keep development, CI, and release on the same lock file.
- Pin SynthPilot and GitHub Actions to immutable versions/revisions.
- Verify wheel build, wheel install, and `digital-ic-agent --diagnostic`.

SynthPilot is pinned in configuration as `uvx synthpilot==0.1.0`. Real
SynthPilot MCP validation remains blocked by the recorded license device-limit
issue and is still tracked in the P0-1 follow-up.

## User Journeys

1. As a user installing from a wheel, I can run `digital-ic-agent --diagnostic`
   without depending on the source checkout layout.
2. As a maintainer, I can update the package version in one source file and have
   package metadata follow it.
3. As a CI reviewer, I can verify GitHub Actions use immutable commit SHAs.
4. As a Vivado user, I can point the tool at Vivado through explicit config or
   environment variables, including an unwrapped executable path.

## Task Report

### Vivado Path Configuration

- RED:
  `uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults --basetemp .tmp-pytest-p1-4-vivado-config-red -p no:cacheprovider -q`
- RED result:
  `1 failed in 0.16s`, proving `.trae/agent/adapters/vivado.py` still contained
  `D:\vivado\2025.2\Vivado\bin\...` machine-specific defaults.
- GREEN:
  `uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults --basetemp .tmp-pytest-p1-4-vivado-config-green -p no:cacheprovider -q`
- GREEN result:
  `1 passed in 0.15s`.

Implementation now resolves Vivado in this order:

1. Explicit `agent.vivado_command`.
2. `DIGITAL_IC_AGENT_VIVADO`.
3. `VIVADO_PATH`.
4. `shutil.which("vivado")`.

Unwrapped `...\Vivado\bin\unwrapped\win64.o\vivado.exe` paths normalize to
the wrapped `...\Vivado\bin\vivado.bat` command.

### Build Backend, Version, and Entrypoint

- RED:
  `uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version tests/test_quality_config.py::test_p1_4_github_actions_are_pinned_to_commit_shas --basetemp .tmp-pytest-p1-4-supply-chain-red -p no:cacheprovider -q`
- RED result:
  `2 failed in 0.12s`, proving there was no `[build-system]` section and
  workflows still used floating tag references such as `actions/checkout@v4`.
- GREEN:
  `uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version tests/test_quality_config.py::test_p1_4_github_actions_are_pinned_to_commit_shas tests/test_quality_config.py::test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults --basetemp .tmp-pytest-p1-4-packaging-green -p no:cacheprovider -q`
- GREEN result:
  `3 passed in 0.43s`.

Implementation:

- Added `hatchling==1.27.0` as the build backend.
- Changed project version to dynamic metadata from
  `src/digital_ic_agent/__about__.py`.
- Added console script:
  `digital-ic-agent = "digital_ic_agent.agent:main"`.
- Exported `__version__` from `digital_ic_agent`.
- Added `hatchling==1.27.0` to the dev dependency group and
  `requirements-dev.txt`.
- Updated `uv.lock`.

### SynthPilot Version Pinning

- RED:
  `uv run --offline --frozen pytest tests/test_agent.py::test_config_uses_portable_synthpilot_command --basetemp .tmp-pytest-p1-4-synthpilot-pin-red -p no:cacheprovider -q`
- RED result:
  `1 failed in 0.62s`, proving the MCP config still used floating
  `["synthpilot"]` arguments.
- GREEN:
  `uv run --offline --frozen pytest tests/test_agent.py::test_config_uses_portable_synthpilot_command --basetemp .tmp-pytest-p1-4-synthpilot-pin-green -p no:cacheprovider -q`
- GREEN result:
  `1 passed in 0.07s`.

Implementation:

- `.trae/config.json` now uses `uvx synthpilot==0.1.0`.
- `.trae/agent/agent.json` now uses `uvx synthpilot==0.1.0`.
- The license key is not stored or echoed in repository evidence.

### Installed Wheel Runtime Data

- RED:
  `uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version tests/test_quality_config.py::test_p1_4_installed_package_loads_legacy_runtime_from_package_data --basetemp .tmp-pytest-p1-4-wheel-runtime-red -p no:cacheprovider -q`
- RED result:
  `2 failed in 0.14s`, proving wheel config did not force-include the runtime
  and `_legacy.py` still only pointed at the source checkout layout.
- GREEN:
  `uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version tests/test_quality_config.py::test_p1_4_installed_package_loads_legacy_runtime_from_package_data --basetemp .tmp-pytest-p1-4-wheel-runtime-green-2 -p no:cacheprovider -q`
- GREEN result:
  `2 passed in 0.10s`.

Implementation:

- `pyproject.toml` force-includes `.trae/agent` as
  `digital_ic_agent/_legacy_agent`.
- `pyproject.toml` force-includes `.trae/skills` as
  `digital_ic_agent/skills`.
- `src/digital_ic_agent/_legacy.py` prefers installed package runtime data and
  falls back to the source checkout layout for development.

### Wheel Build and Fresh Install Diagnostic

Command:

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv run --offline --frozen pytest tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version tests/test_quality_config.py::test_p1_4_installed_package_loads_legacy_runtime_from_package_data tests/test_quality_config.py::test_p1_4_github_actions_are_pinned_to_commit_shas tests/test_quality_config.py::test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults --basetemp .tmp-pytest-p1-4-package-skills-path-green -p no:cacheprovider -q; uv build --wheel --out-dir .tmp-p1-4-dist-skills-path; $wheel = Get-ChildItem .tmp-p1-4-dist-skills-path -Filter 'digital_ic_agent-*.whl' | Sort-Object LastWriteTime -Descending | Select-Object -First 1; python -c "import sys, zipfile; z=zipfile.ZipFile(sys.argv[1]); names=z.namelist(); required=['digital_ic_agent/_legacy_agent/agent.py','digital_ic_agent/_legacy_agent/agent_config.py','digital_ic_agent/skills/digital-ic-designer/SKILL.md','digital_ic_agent/skills/digital-ic-rtl-designer/SKILL.md','digital_ic_agent/skills/digital-ic-verifier/SKILL.md','digital_ic_agent-1.0.0.dist-info/entry_points.txt']; print('\n'.join(name for name in names if name in required)); missing=[name for name in required if name not in names]; assert not missing, missing" $wheel.FullName; python -m venv .tmp-p1-4-wheel-venv-skills-path; .\.tmp-p1-4-wheel-venv-skills-path\Scripts\python.exe -m pip install --no-index --find-links .tmp-p1-4-dist-skills-path $wheel.FullName; $env:DIGITAL_IC_AGENT_VIVADO='D:\vivado\2025.2\Vivado\bin\unwrapped\win64.o\vivado.exe'; .\.tmp-p1-4-wheel-venv-skills-path\Scripts\digital-ic-agent.exe --diagnostic
```

Result:

```text
4 passed in 0.16s
Successfully built .tmp-p1-4-dist-skills-path\digital_ic_agent-1.0.0-py3-none-any.whl
digital_ic_agent/_legacy_agent/agent.py
digital_ic_agent/_legacy_agent/agent_config.py
digital_ic_agent/skills/digital-ic-designer/SKILL.md
digital_ic_agent/skills/digital-ic-rtl-designer/SKILL.md
digital_ic_agent/skills/digital-ic-verifier/SKILL.md
digital_ic_agent-1.0.0.dist-info/entry_points.txt
Successfully installed digital-ic-agent
诊断结果: [OK] 所有工具和技能均已就绪
```

## Test Specification

| # | What is guaranteed | Test file or command | Test type | Result | Evidence |
|---|--------------------|----------------------|-----------|--------|----------|
| 1 | Vivado resolution has no machine-specific default path and honors config/env/PATH discovery | `tests/test_quality_config.py::test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults` | unit/config | PASS | `1 passed in 0.15s`; final `5 passed in 0.23s` |
| 2 | Package uses pinned Hatchling backend, dynamic version source, and console script | `tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version` | config | PASS | `3 passed in 0.43s`; final `5 passed in 0.23s` |
| 3 | Installed package can locate legacy runtime from package data with source fallback | `tests/test_quality_config.py::test_p1_4_installed_package_loads_legacy_runtime_from_package_data` | config/install | PASS | `2 passed in 0.10s`; final `5 passed in 0.23s` |
| 4 | GitHub Actions workflow `uses:` references are immutable 40-character commit SHAs | `tests/test_quality_config.py::test_p1_4_github_actions_are_pinned_to_commit_shas` | supply-chain | PASS | `3 passed in 0.43s`; final `5 passed in 0.23s` |
| 5 | SynthPilot MCP launch command is portable and version-pinned | `tests/test_agent.py::test_config_uses_portable_synthpilot_command` | config/supply-chain | PASS | `1 passed in 0.07s` |
| 6 | Lock file remains current after adding Hatchling and dynamic version metadata | `uv lock --check` | supply-chain | PASS | `Resolved 17 packages in 1ms` |
| 7 | Frozen dev install uses the same lock file | `uv sync --offline --frozen --group dev` | install | PASS | `Checked 16 packages in 7ms` |
| 8 | Wheel contains runtime, default skills, and console entry point | `uv build --wheel` plus zip inspection | package/install | PASS | required files printed and no missing assertion |
| 9 | Fresh wheel install can run `digital-ic-agent --diagnostic` | fresh venv + wheel install + diagnostic | install/runtime | PASS | `诊断结果: [OK] 所有工具和技能均已就绪` |
| 10 | Focused source passes Ruff and Mypy after P1-4 changes | quality commands | quality/typecheck | PASS | `All checks passed!`; `Success: no issues found in 62 source files` |

## Quality Commands

```powershell
$env:UV_CACHE_DIR='F:\My_code\Agent_design_for_vivado\.tmp\uv-cache'; uv lock --check; uv sync --offline --frozen --group dev; uv run --offline --frozen pytest tests/test_agent.py::test_config_uses_portable_synthpilot_command tests/test_quality_config.py::test_p1_4_package_has_reproducible_build_backend_entrypoint_and_version tests/test_quality_config.py::test_p1_4_installed_package_loads_legacy_runtime_from_package_data tests/test_quality_config.py::test_p1_4_github_actions_are_pinned_to_commit_shas tests/test_quality_config.py::test_p1_4_vivado_resolution_uses_env_or_discovery_not_machine_defaults --basetemp .tmp-pytest-p1-4-final-quality -p no:cacheprovider -q; uv run --offline --frozen ruff check .trae/agent src tests/test_agent.py tests/test_quality_config.py; uv run --offline --frozen mypy
```

Result:

```text
Resolved 17 packages in 1ms
Checked 16 packages in 7ms
5 passed in 0.23s
All checks passed!
Success: no issues found in 62 source files
```

## Known Gaps

- SynthPilot version pinning is completed at configuration level as
  `uvx synthpilot==0.1.0`; real MCP initialize/tools/list/tool-call validation
  remains blocked by the previously recorded license device-limit issue.
- This slice validates the provided unwrapped Vivado executable path and PATH
  discovery via tests, plus installed-wheel diagnostic with
  `DIGITAL_IC_AGENT_VIVADO`. A second physical Vivado installation path still
  needs evidence if the acceptance standard requires two real installations
  rather than two resolution mechanisms.
- Full test suite was not rerun here; the P1-4 focused tests, lock/frozen
  install, wheel install diagnostic, Ruff, and Mypy were rerun.
