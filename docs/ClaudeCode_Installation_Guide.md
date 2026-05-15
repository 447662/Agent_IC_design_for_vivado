# ClaudeCode 安装指引

## 目录

1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
   - 2.1 安装 Python 环境
   - 2.2 安装 ClaudeCode CLI
   - 2.3 配置 API Key
   - 2.4 安装 Trae 插件
3. [配置说明](#配置说明)
4. [验证安装](#验证安装)
5. [常见问题](#常见问题)
6. [高级配置](#高级配置)

---

## 1. 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 (64位) |
| Python | 3.8 或更高版本 |
| 内存 | 至少 8GB RAM |
| 存储空间 | 至少 10GB 可用空间 |
| 网络 | 需要联网进行安装和API调用 |

---

## 2. 安装步骤

### 2.1 安装 Python 环境

#### 方式一：使用 uv (推荐)

```bash
# 安装 uv (Python包管理器)
powershell -Command "Invoke-WebRequest -Uri https://astral.sh/uv/install.sh -OutFile install-uv.sh; bash install-uv.sh"

# 验证安装
uv --version
```

#### 方式二：使用官方安装包

1. 访问 [Python官网](https://www.python.org/downloads/)
2. 下载 Python 3.8+ 安装包
3. 运行安装程序，勾选 "Add Python to PATH"
4. 验证安装：
   ```bash
   python --version
   ```

### 2.2 安装 ClaudeCode CLI

```bash
# 使用 uv 安装
uv tool install claude-code

# 或使用 pip
pip install claude-code
```

### 2.3 配置 API Key

#### 方法一：环境变量配置

```bash
# 设置环境变量（临时）
setx ANTHROPIC_API_KEY "your-api-key-here"

# 设置环境变量（永久，需要重启终端）
setx ANTHROPIC_API_KEY "your-api-key-here" /M
```

#### 方法二：配置文件

创建 `~/.claude/config.toml` 文件：

```toml
[api]
key = "your-api-key-here"
model = "claude-3-5-sonnet-20240620"
```

### 2.4 安装 Trae 插件

```bash
# 安装 Trae CLI
uv tool install trae-cli

# 初始化 Trae 项目
trae init

# 安装 ClaudeCode 插件
trae plugin install claude-code
```

---

## 3. 配置说明

### 3.1 项目级配置

在项目根目录创建 `.trae/config.json`：

```json
{
  "mcpServers": {
    "claude": {
      "command": "claude",
      "args": ["api", "serve"],
      "env": {
        "ANTHROPIC_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### 3.2 全局配置

创建 `~/.trae/config.json`：

```json
{
  "defaults": {
    "model": "claude-3-5-sonnet",
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

---

## 4. 验证安装

### 4.1 基础验证

```bash
# 检查 ClaudeCode 版本
claude --version

# 测试 API 连接
claude ask "Hello, Claude!"
```

### 4.2 在 Trae 中验证

```bash
# 进入 Trae 交互式模式
trae

# 在 Trae 中测试
> ask Claude "What is Python?"
```

### 4.3 测试技能调用

```bash
# 创建测试技能
trae skill create test-skill

# 运行技能
trae run test-skill
```

---

## 5. 常见问题

### Q1: API Key 无效

**问题描述**：收到 "Invalid API Key" 错误

**解决方案**：
1. 检查 API Key 是否正确复制
2. 确保 API Key 没有过期
3. 检查网络连接
4. 验证环境变量是否正确设置

```bash
# 检查环境变量
echo %ANTHROPIC_API_KEY%
```

### Q2: 安装失败

**问题描述**：pip/uv 安装失败

**解决方案**：
```bash
# 更新 pip
python -m pip install --upgrade pip

# 使用国内镜像
pip install claude-code -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用 uv
uv tool install claude-code --index https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q3: Trae 插件加载失败

**问题描述**：Trae 无法加载 ClaudeCode 插件

**解决方案**：
```bash
# 检查插件是否安装
trae plugin list

# 重新安装插件
trae plugin uninstall claude-code
trae plugin install claude-code
```

### Q4: 网络连接问题

**问题描述**：无法连接到 Anthropic API

**解决方案**：
1. 检查网络连接
2. 配置代理（如需要）
```bash
setx HTTP_PROXY "http://proxy:port"
setx HTTPS_PROXY "https://proxy:port"
```

---

## 6. 高级配置

### 6.1 多模型支持

```json
{
  "mcpServers": {
    "claude-sonnet": {
      "command": "claude",
      "args": ["api", "serve", "--model", "claude-3-5-sonnet-20240620"]
    },
    "claude-opus": {
      "command": "claude",
      "args": ["api", "serve", "--model", "claude-3-opus-20240229"]
    }
  }
}
```

### 6.2 日志配置

```json
{
  "logging": {
    "level": "DEBUG",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "claude.log"
  }
}
```

### 6.3 自定义技能目录

```json
{
  "skills": {
    "directories": [
      "./.trae/skills",
      "~/.trae/skills"
    ]
  }
}
```

---

## 附录

### API Key 获取方式

1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 登录或注册账号
3. 进入 API Keys 页面
4. 创建新的 API Key
5. 复制并保存 API Key

### 官方文档

- [Claude API 文档](https://docs.anthropic.com/claude/docs/introduction)
- [Trae CLI 文档](https://trae-cli.github.io/docs/)
- [ClaudeCode GitHub](https://github.com/anthropics/claude-code)

---

**文档版本**: v1.0  
**更新日期**: 2026-05-15  
**适用版本**: ClaudeCode 1.0+