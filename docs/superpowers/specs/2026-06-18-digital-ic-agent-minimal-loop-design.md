# 数字 IC Agent 基础 CLI 与设计文档模板闭环设计

日期：2026-06-18

## 背景

当前项目定位为数字 IC 前端设计 Agent，目标覆盖需求分析、设计文档、RTL 实现与验证流程。现有仓库已经具备 Agent 配置、技能说明和 Python 入口脚本，但核心执行逻辑仍以环境诊断、关键词匹配和流程打印为主，尚未形成“输入需求 → 生成项目产物”的闭环。

本设计将项目推进到一个可运行、可测试、边界清晰的原型阶段：修复基础 CLI 和配置问题，并增加设计文档模板生成能力。

## 目标

本次修改采用“基础修复 + 设计文档模板最小闭环”方案。

实现后项目应支持：

1. 使用命令行参数控制 Agent 行为。
2. 单独运行环境诊断。
3. 列出当前配置的技能。
4. 在无 Vivado 或 SynthPilot 环境时，通过显式参数跳过工具检查并体验模板生成。
5. 根据用户自然语言需求生成一份 Markdown 设计说明模板。
6. 通过自动化测试验证技能匹配、CLI 行为和模板输出。

## 非目标

本次不实现以下能力：

1. 自动生成完整可综合 RTL。
2. 自动生成完整 UVM 验证环境。
3. 自动调用 Vivado 完成仿真闭环。
4. 自动综合、时序分析、波形解析或覆盖率统计。
5. 接入真实 LLM 或 Trae skill 运行时进行智能内容生成。

这些能力应在后续设计中独立规划。

## 用户体验

### 查看技能

```bash
python .trae/agent/agent.py --list-skills
```

输出当前 `agent.json` 中配置的技能、描述和触发关键词。

### 环境诊断

```bash
python .trae/agent/agent.py --diagnostic
```

只检查 CLI 工具、MCP 服务和技能文件，不生成设计文档。诊断全部通过时返回 `0`，存在缺失项时返回非零状态码。

### 生成设计文档模板

```bash
python .trae/agent/agent.py --no-tool-check --output-dir outputs "设计一个UART控制器"
```

流程：

1. 解析用户需求。
2. 匹配推荐技能。
3. 因 `--no-tool-check` 跳过外部工具检查。
4. 创建输出目录。
5. 生成 `design_spec.md`。
6. 在终端打印生成路径。

如果未传 `--no-tool-check`，Agent 会先执行环境诊断；缺少必需工具时停止生成，并提示安装指南。

## CLI 设计

`agent.py` 使用 `argparse` 解析参数，支持以下参数：

| 参数 | 作用 |
| --- | --- |
| `requirement` | 用户自然语言设计需求，可由多个命令行片段组成 |
| `--diagnostic` | 只运行环境诊断 |
| `--list-skills` | 列出技能配置 |
| `--output-dir <path>` | 指定产物根目录，默认 `outputs` |
| `--no-tool-check` | 跳过 Vivado、SynthPilot 等外部工具检查 |

行为约定：

1. `--diagnostic`、`--list-skills` 与普通执行模式互斥；同一次调用中只能选择一种模式。
2. `--no-tool-check` 只对普通执行模式有效，若与 `--diagnostic` 或 `--list-skills` 同时出现，视为参数冲突并返回非零状态码。
3. 普通执行模式需要设计需求；无参数时保留交互式输入。
4. 空需求返回非零状态码并打印错误。
5. 工具检查失败时，默认中止普通执行；显式使用 `--no-tool-check` 时继续执行。

## 配置设计

### MCP 配置

将硬编码的个人路径：

```json
"C:\\Users\\Dell\\.local\\bin\\uvx.exe"
```

改为通用命令：

```json
"uvx"
```

参数保持：

```json
["synthpilot"]
```

这样能依赖 PATH 或用户环境中的 `uvx`，避免绑定特定 Windows 用户目录。

### CLI 检查命令

将 `checkCommand` 从字符串改为数组。例如：

```json
"checkCommand": ["vivado", "-version"]
```

这样 Python 代码不需要使用脆弱的 `split()`，并能更可靠地处理带空格或特殊参数的命令。

## 核心组件

现阶段保持单文件主实现，避免过早拆分。`DigitalICAgent` 内部职责按方法划分：

| 方法 | 责任 |
| --- | --- |
| `load_config()` | 读取并解析 `agent.json` |
| `check_cli_tool()` | 检查一个 CLI 工具是否可用 |
| `check_mcp_server()` | 检查一个 MCP 服务是否可用 |
| `analyze_requirement()` | 根据关键词匹配技能 |
| `run_diagnostic()` | 执行完整环境诊断 |
| `list_skills()` | 输出技能清单 |
| `generate_design_spec()` | 生成 Markdown 设计文档模板 |
| `execute_workflow()` | 编排普通执行流程 |

CLI 层新增：

| 函数 | 责任 |
| --- | --- |
| `parse_args()` | 定义和解析命令行参数 |
| `main()` | 根据参数选择诊断、列技能或普通执行流程 |

后续如果项目继续扩展，可以再拆分为 `config.py`、`diagnostic.py`、`generator.py` 和 `cli.py`。

## 普通执行数据流

```text
用户输入需求
  ↓
argparse 解析参数
  ↓
DigitalICAgent 加载 agent.json
  ↓
analyze_requirement() 匹配技能
  ↓
如果未设置 --no-tool-check，则 run_diagnostic()
  ↓
generate_design_spec()
  ↓
写入 outputs/<project-slug>/design_spec.md
  ↓
终端打印生成路径
```

## 设计文档模板内容

生成文件为 Markdown，默认文件名：

```text
outputs/<project-slug>/design_spec.md
```

模板包含：

1. 需求摘要。
2. Agent 匹配结果。
3. 初步设计目标。
4. 建议模块划分。
5. 初步接口定义。
6. 验证计划占位。
7. 后续人工确认项。

模板必须明确它是“初始设计说明模板”，而不是已完成的最终设计文档，避免夸大当前 Agent 能力。

示例结构：

```markdown
# 数字 IC 设计说明模板

## 1. 需求摘要
原始用户需求：...

## 2. Agent 匹配结果
- 推荐技能：...
- 匹配说明：...

## 3. 初步设计目标
- 功能目标：待补充
- 性能目标：待补充
- 接口目标：待补充
- 约束条件：待补充

## 4. 建议模块划分
| 模块 | 职责 | 备注 |
| --- | --- | --- |

## 5. 初步接口定义
| 信号名 | 方向 | 位宽 | 描述 |
| --- | --- | --- | --- |

## 6. 验证计划占位
- 基本功能测试：待补充
- 边界条件测试：待补充
- 异常场景测试：待补充
- 覆盖率目标：待补充

## 7. 后续人工确认项
- 工作频率
- 复位方式
- 总线协议
- 数据宽度
- 时钟域
- 功耗/面积约束
```

## 输出目录命名

Agent 根据用户需求生成一个安全的 project slug，用于输出目录名。规则：

1. 优先从英文、数字、连字符、下划线中提取可用字符。
2. 对中文或无法提取稳定英文名的需求，使用通用前缀加短哈希，例如 `design-a1b2c3d4`。
3. 避免路径穿越字符和平台非法字符。
4. 若目录已存在，允许覆盖同名 `design_spec.md`，因为该文件由本次命令生成；其他文件不主动删除。

## 错误处理

| 场景 | 行为 |
| --- | --- |
| `agent.json` 缺失 | 打印配置文件缺失错误，返回非零状态码 |
| `agent.json` 不是合法 JSON | 打印配置解析错误，返回非零状态码 |
| 用户需求为空 | 打印错误，返回非零状态码 |
| 必需工具缺失 | 默认中止执行并提示安装指南 |
| 使用 `--no-tool-check` | 跳过工具检查并继续生成模板 |
| 输出目录不可写 | 打印路径错误，返回非零状态码 |

## 测试设计

新增 `tests/test_agent.py`，使用 `pytest`。

测试范围：

1. 技能匹配：
   - “生成设计文档”匹配 `digital-ic-designer`。
   - “实现 UART Verilog”匹配 `digital-ic-rtl-designer`。
   - “使用 UVM 前仿”匹配 `digital-ic-verifier`。
   - 无关键词时默认匹配 `digital-ic-rtl-designer`。

2. CLI 行为：
   - `--list-skills` 返回成功。
   - `--diagnostic` 可以独立运行。
   - `--no-tool-check` 可以在无外部 EDA 工具环境下生成文档。

3. 输出生成：
   - `design_spec.md` 被创建。
   - 文档包含原始用户需求。
   - 文档包含匹配技能名称。
   - 输出目录位于 `--output-dir` 指定路径下。

新增 `requirements-dev.txt`，包含：

```text
pytest
```

当前运行代码只依赖 Python 标准库，不需要运行时 `requirements.txt`。

## 文档更新

更新以下文档：

1. `README.md`
   - 标明当前能力边界。
   - 增加 `--diagnostic`、`--list-skills`、`--no-tool-check`、`--output-dir` 示例。
   - 增加最小闭环输出说明。

2. `.trae/agent/README.md`
   - 同步 CLI 行为。
   - 删除不存在的 `requirements.txt` 安装说明。
   - 说明 `requirements-dev.txt` 仅用于测试。

3. `.trae/agent/agent.json`
   - 更新 MCP 命令和 CLI 检查命令格式。

4. `.trae/config.json`
   - 更新 SynthPilot 命令为 `uvx`。

## 版本管理策略

本次可以安全新增或修改：

1. Agent 代码。
2. Agent 配置。
3. README 文档。
4. 测试文件。
5. 开发依赖文件。
6. `.gitignore` 中针对 `.claude/worktrees/` 的忽略规则。

`.claude/settings.local.json` 当前已被 Git 跟踪且存在本地修改。本次不删除、不取消跟踪该文件；如果后续要移出版本管理，应单独征得用户确认后处理。

## 验收标准

实现完成后，以下命令应满足预期：

```bash
python .trae/agent/agent.py --list-skills
```

能列出 3 个技能并返回成功。

```bash
python .trae/agent/agent.py --diagnostic
```

能执行诊断。环境完整时返回成功；缺失必需工具时返回非零状态码并给出安装提示。

```bash
python .trae/agent/agent.py --no-tool-check --output-dir outputs "设计一个UART控制器"
```

能生成 `outputs/<project-slug>/design_spec.md`，终端打印生成路径，文档包含用户需求和匹配技能。

```bash
pytest
```

测试通过。

## 后续扩展方向

本次改造完成后，下一阶段可以考虑：

1. 将 `generate_design_spec()` 替换或增强为 LLM 辅助生成。
2. 为 RTL 技能生成工程骨架和 testbench 模板。
3. 接入 Vivado 或 Verilator 做 smoke simulation。
4. 将 `DigitalICAgent` 拆分为更细粒度模块。
5. 为 `agent.json` 增加 JSON Schema 校验。
