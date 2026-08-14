# ChatGPT DeepSeek 模型切换助手

让非研发人员也能在 ChatGPT（内置 Codex）中一键切换 DeepSeek 模型，安全、无需手动修改配置文件。

**A Codex skill that lets non-developers safely switch DeepSeek models in ChatGPT/Codex — no manual config editing required.**

## 功能特性 / Features

- 首次接入 DeepSeek，自动写入模型元数据与配置 / First-time DeepSeek setup with automatic catalog and config
- 在 `deepseek-v4-flash` 与 `deepseek-v4-pro` 之间一键切换 / Switch between flash and pro
- 一键切回 OpenAI 默认模型 / Switch back to the OpenAI default
- 重新设置 API Key / Replace the API key
- 查看当前模型状态 / Check the current model status
- 从备份恢复最近一次改动 / Restore the latest change from backup

## 环境要求 / Requirements

- ChatGPT 桌面端（内置 Codex）、Codex CLI 或 VS Code 的 Codex 插件 / ChatGPT desktop (Codex built-in), Codex CLI, or the Codex VS Code extension
- Python 3.8+；Windows 上使用 `python`（或 `py -3`）代替 `python3` / Python 3.8+; on Windows use `python` (or `py -3`) instead of `python3`

## 安装 / Installation

将技能目录放入 Codex 技能目录（默认 `~/.codex/skills`，若设置了 `CODEX_HOME` 请放入对应目录），重启 ChatGPT / Codex 后自动生效。

macOS / Linux:

```bash
git clone git@github.com:BingBlog/chatgpt-deepseek-model-switch.git ~/.codex/skills/chatgpt-deepseek-model-switch
```

Windows (PowerShell):

```powershell
git clone git@github.com:BingBlog/chatgpt-deepseek-model-switch.git "$HOME\.codex\skills\chatgpt-deepseek-model-switch"
```

## 使用方法 / Usage

对 Codex 说一句自然语言即可，例如："帮我切换到 DeepSeek pro"、"换回 flash"、"切回 OpenAI 默认"、"重新设置 API Key"。

底层命令 / Underlying commands（在技能目录内执行）:

| 操作 / Action | 命令 / Command |
| --- | --- |
| 查看状态 / Status | `python3 scripts/deepseek_switch.py status` |
| 首次配置 / Setup | `DEEPSEEK_API_KEY=<key> python3 scripts/deepseek_switch.py setup` |
| 切换 flash / pro | `python3 scripts/deepseek_switch.py switch flash` / `switch pro` |
| 切回 OpenAI 默认 | `python3 scripts/deepseek_switch.py switch openai` |
| 重新设置 Key | `DEEPSEEK_API_KEY=<key> python3 scripts/deepseek_switch.py set-key` |
| 恢复备份 / Restore | `python3 scripts/deepseek_switch.py restore --latest` |

切换后请重启 ChatGPT（或 Codex）或开新会话生效。

## 安全机制 / Safety

- 每次写入前自动备份到 `~/.codex/backup-deepseek/`
- 只修改必要字段，不影响插件、MCP、项目信任等其他配置
- API Key 永不回显
- 写入后自动校验，失败自动回滚

## 常见问题 / FAQ

- **切换后没有变化？** 重启 ChatGPT / Codex 或开新会话。
- **历史会话不见了？** 会话按登录方式分组，切回对应提供方后恢复显示，不会被删除。
- **没有 API Key？** 到 [DeepSeek Platform](https://platform.deepseek.com/api_keys) 获取（以 `sk-` 开头）。

## 相关链接 / Links

- DeepSeek 官方接入文档：[Integrate with Codex](https://api-docs.deepseek.com/quick_start/agent_integrations/codex/)
- 技能内部参考：`references/setup.md`
- 自动化测试：`tests/run_tests.sh`
