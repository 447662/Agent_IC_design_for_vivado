from typing import Any
import hashlib
import re
from pathlib import Path


def build_default_project_slug(user_input: Any) -> str:
    ascii_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(user_input).lower())
    ascii_slug = re.sub(r"-+", "-", ascii_slug).strip("-_")
    if ascii_slug:
        return ascii_slug[:48].strip("-_")

    digest = hashlib.sha1(str(user_input).encode("utf-8")).hexdigest()[:8]
    return "design-{}".format(digest)


def render_default_design_spec(
    user_input: Any,
    matched_skills: Any,
    skill_mapping: Any,
) -> str:
    skill_lines = []
    for skill_name in matched_skills:
        skill = skill_mapping.get(skill_name, {"description": "未知技能"})
        skill_lines.append("- `{}`：{}".format(skill_name, skill["description"]))

    skill_text = "\n".join(skill_lines)

    return """# 数字 IC 设计说明模板

> 本文档由 Digital IC Frontend Agent 自动生成，是用于启动设计讨论的初始设计说明模板，不代表最终 RTL、UVM 或签核结果。

## 1. 需求摘要

原始用户需求：

```text
{user_input}
```

## 2. Agent 匹配结果

推荐技能：

{skill_text}

匹配说明：Agent 根据需求关键词和默认路由规则推荐以上技能。若需求没有明确命中设计文档、RTL 或 UVM 关键词，则默认进入 RTL 设计流程。

## 3. 初步设计目标

- 功能目标：需用户确认模块功能、协议行为和异常处理要求。
- 性能目标：需用户确认工作频率、吞吐率、延迟和资源预算。
- 接口目标：需用户确认总线协议、数据宽度、地址宽度和握手机制。
- 约束条件：需用户确认目标器件、工艺节点、复位策略和时钟域数量。

## 4. 建议模块划分

| 模块 | 职责 | 备注 |
| --- | --- | --- |
| 顶层控制模块 | 集成子模块并暴露外部接口 | 需结合协议和时钟域细化 |
| 寄存器/配置模块 | 保存配置项和状态信息 | 若设计不需要软件配置，可移除 |
| 数据通路模块 | 处理核心数据流 | 需根据位宽和吞吐目标细化 |
| 状态机模块 | 管理协议阶段和控制流程 | 需补充状态转移图 |

## 5. 初步接口定义

| 信号名 | 方向 | 位宽 | 描述 |
| --- | --- | --- | --- |
| clk | input | 1 | 主时钟 |
| rst_n | input | 1 | 低有效复位 |
| data_in | input | 需确认 | 输入数据 |
| data_out | output | 需确认 | 输出数据 |
| valid | input/output | 1 | 数据有效指示，方向需按模块角色确认 |
| ready | input/output | 1 | 反压握手信号，方向需按模块角色确认 |

## 6. 验证计划占位

- 基本功能测试：覆盖正常配置、正常传输和基本状态转移。
- 边界条件测试：覆盖最小/最大数据宽度、连续传输和空闲切换。
- 异常场景测试：覆盖复位中断、非法配置、协议错误和超时场景。
- 覆盖率目标：后续确认语句覆盖率、分支覆盖率、功能覆盖率目标。

## 7. 后续人工确认项

- 工作频率
- 复位方式
- 总线协议
- 数据宽度
- 地址宽度
- 时钟域数量
- 是否需要 UVM 验证
- 功耗、面积和时序约束
""".format(user_input=user_input, skill_text=skill_text)


def write_default_design_spec(
    user_input: Any,
    matched_skills: Any,
    output_dir: Any,
    skill_mapping: Any,
) -> Path:
    output_root = Path(output_dir)
    project_dir = output_root / build_default_project_slug(user_input)
    project_dir.mkdir(parents=True, exist_ok=True)
    spec_path = project_dir / "design_spec.md"
    spec_path.write_text(
        render_default_design_spec(user_input, matched_skills, skill_mapping),
        encoding="utf-8",
    )
    return spec_path
