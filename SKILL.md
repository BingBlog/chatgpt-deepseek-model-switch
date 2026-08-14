---
name: chatgpt-deepseek-model-switch
description: 为 ChatGPT（桌面端内置 Codex，含 Codex CLI 与 VS Code 插件）配置并使用 DeepSeek 模型，面向非研发用户：首次接入 DeepSeek（写入 models.json 与 config.toml、安全设置 API Key）、在 deepseek-v4-flash 与 deepseek-v4-pro 之间切换、一键切回 OpenAI 默认模型、重新设置 API Key、查看当前模型状态或从备份恢复。当用户说"用 DeepSeek/切换到 DeepSeek/换 flash 或 pro/切回 OpenAI 默认/重新设置 API Key/现在用的什么模型/DeepSeek 用不了"时使用。
---

# ChatGPT DeepSeek 模型切换

## 原则

- 用户多为非研发人员：全程中文沟通，绝不要求用户手动编辑 `~/.codex` 下的配置文件。
- ChatGPT 桌面端与 Codex CLI、VS Code 插件共用同一份配置，本技能对三端都生效。
- 脚本统一入口：`<技能目录>/scripts/deepseek_switch.py`，所有操作都通过 `python3 <该路径> <子命令>` 执行。
- 切换只改必要字段，插件、MCP、项目信任等其他配置一律不动；每次写操作前自动备份到 `~/.codex/backup-deepseek/`。
- API Key 是敏感信息：在对话中向用户索要，通过 `DEEPSEEK_API_KEY` 环境变量传给脚本（或 `--api-key-stdin`）；不要回显 Key，不要写进代码或日志。
- 切换后必须重启 ChatGPT（或 Codex CLI / VS Code 插件）或开新会话才生效；历史会话按登录方式分组，切回 OpenAI 后 DeepSeek 会话只是隐藏，不是丢失。

## 工作流

1. 先运行 `status` 查看当前状态。
2. 按用户意图选择操作（见下表）。
3. 校验通过后，向用户说明当前模型、Key 状态和"重启才生效"的注意事项。

| 用户意图 | 命令 |
| --- | --- |
| 首次使用 DeepSeek | 先向用户索要 API Key（sk- 开头），再运行 `DEEPSEEK_API_KEY=<key> python3 <脚本> setup --model flash`（或 `--model pro`） |
| 切换到 flash / pro | `python3 <脚本> switch flash` / `switch pro` |
| 切回 OpenAI 默认 | `python3 <脚本> switch openai` |
| 重新设置 API Key | `DEEPSEEK_API_KEY=<key> python3 <脚本> set-key` |
| 查看当前状态 | `python3 <脚本> status` |
| 手动恢复最近一次改动 | `python3 <脚本> restore --latest` |

## 模型说明

- `deepseek-v4-flash`：日常任务，响应快。
- `deepseek-v4-pro`：复杂任务，推理更强。
- 两者共用同一个 API Key 与 base_url，切换只改配置中的 `model` 字段，秒级生效（重启后）。

## 首次配置要点

- `setup` 会把 `assets/deepseek-models.json` 中的两个 DeepSeek 模型合并进 `CODEX_HOME/models.json`，不会覆盖已有模型条目。
- `setup` 会记录改动前各字段的原值到 `~/.codex/backup-deepseek/state.json`，保证"切回 OpenAI"是精确还原而非整份覆盖。
- 用户没有 Key 时，引导其到 https://platform.deepseek.com/api_keys 获取。

## 异常处理

- 脚本写完后自动校验，校验失败会自动回滚并提示，无需用户处理。
- `status` 显示未配置、或 `switch` 报"尚未配置"：先执行 `setup`。
- Key 失效（401 / 鉴权失败）：执行 `set-key`。
- 校验或行为异常仍无法解决：读取 `references/setup.md` 的排障章节。

## 参考

- 配置字段说明、官方脚本备选与排障：`references/setup.md`（出现异常时再读取）。
