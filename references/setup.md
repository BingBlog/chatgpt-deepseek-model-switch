# DeepSeek 接入 Codex 参考

官方来源：https://api-docs.deepseek.com/quick_start/agent_integrations/codex/

## 目录

- 配置字段说明
- 模型元数据（models.json）
- 官方一键脚本（备选）
- API Key
- 会话与生效说明
- 故障排查

## 配置字段说明

| 字段 | 作用 |
| --- | --- |
| `model` | 默认使用的模型（`deepseek-v4-flash` / `deepseek-v4-pro`） |
| `model_provider` | 使用的模型提供方，对应 `[model_providers.<id>]` 的 id |
| `preferred_auth_method`、`forced_login_method` | 使用 API Key 认证，跳过 ChatGPT 账号登录 |
| `model_reasoning_effort` | 推理强度（本技能默认 `high`） |
| `model_catalog_json` | 自定义模型目录文件（models.json）路径 |
| `[model_providers.deepseek]` 的 `name` | 提供方显示名称 |
| `[model_providers.deepseek]` 的 `base_url` | DeepSeek API 地址（`https://api.deepseek.com/`） |
| `[model_providers.deepseek]` 的 `wire_api` | 通信协议，`responses` 表示 Responses API |
| `[model_providers.deepseek]` 的 `experimental_bearer_token` | API Key |

## 模型元数据（models.json）

`models.json` 向 Codex 声明模型的能力元数据：上下文窗口、推理强度档位、工具调用格式等。本技能将两份官方模型定义打包在 `assets/deepseek-models.json`，`setup` 时合并进 `CODEX_HOME/models.json`。

## 官方一键脚本（备选）

官方也提供一键脚本，效果等价，但为交互式菜单：

```bash
bash <(curl -fsSL https://cdn.deepseek.com/api-docs/codex-deepseek-setup.sh)
```

本技能的 `setup` 是非交互实现，更适合 Codex 代为操作。

## API Key

- 获取地址：https://platform.deepseek.com/api_keys
- 以 `sk-` 开头。
- 通过 `DEEPSEEK_API_KEY` 环境变量或 `--api-key-stdin` 传入脚本；不要写入命令历史、日志或代码。

## 会话与生效说明

- Codex CLI、ChatGPT 桌面端、VS Code 插件共用 `~/.codex` 下的同一份配置，配一次即可。
- 修改配置后需重启客户端或开新会话才生效。
- 会话记录按登录方式分组：切到 DeepSeek 后看不到 OpenAI 订阅的会话、切回后看不到 DeepSeek 的会话，都是隐藏而非删除。

## 故障排查

| 现象 | 处理 |
| --- | --- |
| `status` 显示 DeepSeek 未配置 | 执行 `setup` |
| 401 / API Key 无效 | 执行 `set-key` 换新 Key |
| 切换后模型未变化 | 未重启：重启 Codex / 开新会话 |
| 校验失败 | 脚本已自动回滚；重试操作，仍失败则 `restore --latest` |
| 历史会话不见了 | 登录分组所致，切换回对应提供方后恢复显示 |
| 未用本技能 `setup` 过就直接 `switch openai`（如官方脚本配的） | 脚本会安全移除 DeepSeek 相关字段，其他配置保留；之后要回到 DeepSeek 请执行 `setup` |
