#!/usr/bin/env python3
"""Switch Codex between DeepSeek models and the OpenAI default configuration.

Safe, surgical edits to ~/.codex/config.toml and models.json for non-developer
users. Every write is preceded by a backup and followed by validation; on
validation failure the previous state is restored automatically.

Commands:
  status                       Show the current model/provider state (read-only)
  setup [--model flash|pro]    First-time DeepSeek configuration
  switch flash|pro|openai      Switch the active model/provider
  set-key                      Replace the DeepSeek API key
  restore --latest             Restore the most recent backup of config files

The config directory is $CODEX_HOME when set, otherwise ~/.codex.
The API key must be provided via the DEEPSEEK_API_KEY environment variable or
--api-key-stdin. It is never echoed to the terminal or written to logs.
"""

from __future__ import print_function

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path


MANAGED_KEYS = (
    "model",
    "model_provider",
    "preferred_auth_method",
    "forced_login_method",
    "model_reasoning_effort",
    "model_catalog_json",
)
DEEPSEEK_TABLE = "model_providers.deepseek"
DEEPSEEK_MODELS = ("deepseek-v4-flash", "deepseek-v4-pro")
DEEPSEEK_FIELDS = {
    "name": "deepseek",
    "base_url": "https://api.deepseek.com/",
    "wire_api": "responses",
}
HEADER_RE = re.compile(r"^\s*\[")
TABLE_RE = re.compile(r"^\s*\[\s*([^\]]+)\s*\]\s*$")


# ---------------------------------------------------------------------------
# TOML helpers (line-based, surgical; preserves all other content/comments)
# ---------------------------------------------------------------------------

def toml_quote(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_lines(path):
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def top_level_end(lines):
    """Index of the first [section] header; len(lines) when there is none."""
    for i, line in enumerate(lines):
        if HEADER_RE.match(line):
            return i
    return len(lines)


def _key_pattern(key):
    return re.compile(r"^\s*" + re.escape(key) + r"\s*=")


def get_top_level(lines, key):
    end = top_level_end(lines)
    pattern = _key_pattern(key)
    for i in range(end):
        match = pattern.match(lines[i])
        if not match:
            continue
        rest = lines[i][match.end():].strip()
        quoted = re.match(r'^"([^"]*)"', rest)
        if quoted:
            return quoted.group(1)
        bare = re.match(r"^(\S+)", rest)
        if bare:
            return bare.group(1)
        return None
    return None


def set_top_level(lines, key, value):
    end = top_level_end(lines)
    pattern = _key_pattern(key)
    new_line = "%s = %s\n" % (key, toml_quote(value))
    for i in range(end):
        if pattern.match(lines[i]):
            lines[i] = new_line
            return
    lines.insert(end, new_line)


def remove_top_level(lines, key):
    end = top_level_end(lines)
    pattern = _key_pattern(key)
    kept = [line for line in lines[:end] if not pattern.match(line)]
    return kept + lines[end:]


def table_block(lines, table):
    start = None
    for i, line in enumerate(lines):
        if TABLE_RE.match(line) and TABLE_RE.match(line).group(1) == table:
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if HEADER_RE.match(lines[i]):
            end = i
            break
    return (start, end)


def set_table_field(lines, table, key, value):
    block = table_block(lines, table)
    new_line = "%s = %s\n" % (key, toml_quote(value))
    if block is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append("[%s]\n" % table)
        for field, field_value in DEEPSEEK_FIELDS.items():
            lines.append("%s = %s\n" % (field, toml_quote(field_value)))
        lines.append(new_line)
        return
    start, end = block
    pattern = _key_pattern(key)
    for i in range(start + 1, end):
        if pattern.match(lines[i]):
            lines[i] = new_line
            return
    lines.insert(end, new_line)


def remove_table(lines, table):
    block = table_block(lines, table)
    if block is None:
        return lines
    start, end = block
    return lines[:start] + lines[end:]


def replace_table(lines, table, snapshot_lines):
    block = table_block(lines, table)
    if block is not None:
        start, end = block
        return lines[:start] + list(snapshot_lines) + lines[end:]
    if not snapshot_lines:
        return lines
    result = list(lines)
    if result and not result[-1].endswith("\n"):
        result[-1] += "\n"
    if result and result[-1].strip():
        result.append("\n")
    result.extend(snapshot_lines)
    return result


# ---------------------------------------------------------------------------
# State / backup
# ---------------------------------------------------------------------------

def config_dir():
    home = os.environ.get("CODEX_HOME")
    if home:
        return Path(home).expanduser()
    return Path.home() / ".codex"


def paths(cdir):
    return {
        "config": cdir / "config.toml",
        "models": cdir / "models.json",
        "backup": cdir / "backup-deepseek",
        "state": cdir / "backup-deepseek" / "state.json",
    }


def load_state(state_path):
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (ValueError, OSError):
            pass
    return {}


def save_state(state_path, state):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def backup_now(config_path, models_path, backup_dir, keep=10):
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if config_path.exists():
        shutil.copy2(config_path, backup_dir / ("config.%s.toml" % stamp))
    if models_path.exists():
        shutil.copy2(models_path, backup_dir / ("models.%s.json" % stamp))
    for prefix in ("config.", "models."):
        glob = "config.*.toml" if prefix == "config." else "models.*.json"
        files = sorted(backup_dir.glob(glob))
        for old in files[:-keep]:
            old.unlink()


def latest_backups(backup_dir):
    configs = sorted(backup_dir.glob("config.*.toml"))
    models = sorted(backup_dir.glob("models.*.json"))
    return (configs[-1] if configs else None, models[-1] if models else None)


def restore_latest(backup_dir, config_path, models_path):
    config_bak, models_bak = latest_backups(backup_dir)
    restored = []
    if config_bak:
        shutil.copy2(config_bak, config_path)
        restored.append(str(config_bak.name))
    if models_bak:
        shutil.copy2(models_bak, models_path)
        restored.append(str(models_bak.name))
    return restored


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_config(config_path):
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib is not None:
        try:
            with open(config_path, "rb") as handle:
                data = tomllib.load(handle)
            return True, "TOML 语法校验通过（%d 个顶层段）" % len(data)
        except Exception as exc:
            return False, "TOML 校验失败：%s" % exc
    # Lightweight fallback for Python < 3.11: every non-blank, non-comment line
    # must be a header or a key = value pair, and managed keys must be unique.
    try:
        lines = read_lines(config_path)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if HEADER_RE.match(line) or re.match(r"^\S+\s*=", stripped):
                continue
            return False, "第 %d 行不是合法的 TOML：%s" % (i + 1, stripped)
        for key in MANAGED_KEYS:
            occurrences = 0
            for line in lines[:top_level_end(lines)]:
                if _key_pattern(key).match(line):
                    occurrences += 1
            if occurrences > 1:
                return False, "顶层字段 %s 重复出现" % key
        return True, "基础语法校验通过（当前 Python 无 tomllib，仅做结构检查）"
    except Exception as exc:
        return False, "配置读取失败：%s" % exc


def validate_models(models_path):
    if not models_path.exists():
        return False, "models.json 不存在"
    try:
        data = json.loads(models_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return False, "models.json 解析失败：%s" % exc
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return False, "models.json 缺少 models 列表"
    return True, "models.json 校验通过（%d 个模型条目）" % len(models)


def finish_write(config_path, models_path, backup_dir, label):
    ok, msg = validate_config(config_path)
    if ok:
        mok, mmsg = validate_models(models_path)
        if mok:
            print("[OK] %s：%s；%s" % (label, msg, mmsg))
            return
        ok, msg = False, mmsg
    restored = restore_latest(backup_dir, config_path, models_path)
    print("[FAILED] %s：%s" % (label, msg))
    if restored:
        print("[ROLLBACK] 已自动回滚：%s" % ", ".join(restored))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

def ensure_deepseek_models(models_path):
    asset = Path(__file__).resolve().parent.parent / "assets" / "deepseek-models.json"
    if not asset.exists():
        sys.exit("技能缺少 assets/deepseek-models.json，无法完成首次配置。")
    official = json.loads(asset.read_text(encoding="utf-8")).get("models", [])
    by_slug = {model.get("slug"): model for model in official if model.get("slug")}
    missing = [slug for slug in DEEPSEEK_MODELS if slug not in by_slug]
    if missing:
        sys.exit("技能资产中缺少模型定义：%s" % ", ".join(missing))

    data = {"models": []}
    if models_path.exists():
        try:
            existing = json.loads(models_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("models"), list):
                data = existing
        except (ValueError, OSError):
            pass
    slugs = {model.get("slug") for model in data["models"]}
    added = []
    for slug in DEEPSEEK_MODELS:
        if slug not in slugs:
            data["models"].append(by_slug[slug])
            added.append(slug)
    if added:
        models_path.parent.mkdir(parents=True, exist_ok=True)
        models_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("[OK] 已向 models.json 注册模型：%s" % ", ".join(added))
    else:
        print("[OK] models.json 已包含 DeepSeek 模型，无需修改。")


def catalog_value(cdir):
    default = Path.home() / ".codex"
    if cdir == default:
        return "~/.codex/models.json"
    return str(cdir / "models.json")


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------

def resolve_api_key(args):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key and getattr(args, "api_key_stdin", False):
        key = sys.stdin.read().strip()
    if not key:
        sys.exit(
            "未获取到 API Key。请在对话中向用户索要（sk- 开头），"
            "再通过 DEEPSEEK_API_KEY 环境变量传入（不要回显 Key）。"
        )
    if not key.startswith("sk-"):
        sys.exit("API Key 格式不正确：应以 sk- 开头。")
    return key


def mask_key(key):
    if len(key) <= 8:
        return "***"
    return key[:3] + "*" * 8 + key[-4:]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def require_deepseek_table(lines):
    block = table_block(lines, DEEPSEEK_TABLE)
    if block is None:
        sys.exit("DeepSeek 尚未配置。请先执行 setup 完成首次配置。")
    return block


def cmd_status(cdir):
    p = paths(cdir)
    print("CODEX_HOME / 配置目录：%s" % cdir)
    if not p["config"].exists():
        print("状态：config.toml 不存在，Codex 使用默认配置。")
        return
    lines = read_lines(p["config"])
    print("当前模型：%s" % (get_top_level(lines, "model") or "（未指定，默认 OpenAI）"))
    print("模型提供方：%s" % (get_top_level(lines, "model_provider") or "（未指定）"))
    print("认证方式：%s" % (get_top_level(lines, "preferred_auth_method") or "（默认）"))
    print("推理强度：%s" % (get_top_level(lines, "model_reasoning_effort") or "（默认）"))
    print("模型目录：%s" % (get_top_level(lines, "model_catalog_json") or "（默认）"))
    block = table_block(lines, DEEPSEEK_TABLE)
    if block is None:
        print("DeepSeek 提供方：未配置")
    else:
        start, end = block
        table_lines = lines[start:end]
        token = None
        for line in table_lines:
            match = re.match(r'^\s*experimental_bearer_token\s*=\s*"([^"]*)"', line)
            if match:
                token = match.group(1)
        print("DeepSeek 提供方：已配置")
        print("DeepSeek API Key：%s" % (mask_key(token) if token else "未配置"))
    if p["models"].exists():
        ok, msg = validate_models(p["models"])
        print("模型目录文件：%s" % msg)
        try:
            data = json.loads(p["models"].read_text(encoding="utf-8"))
            slugs = [m.get("slug") for m in data.get("models", [])]
            deepseek = [s for s in slugs if s in DEEPSEEK_MODELS]
            print("已注册的 DeepSeek 模型：%s" % (", ".join(deepseek) or "无"))
        except (ValueError, OSError):
            print("模型目录文件：无法解析")
    else:
        print("模型目录文件：不存在")


def snapshot_original_state(lines):
    state = {}
    state["previous_values"] = {
        key: get_top_level(lines, key) for key in MANAGED_KEYS
    }
    block = table_block(lines, DEEPSEEK_TABLE)
    state["deepseek_table_snapshot"] = lines[block[0]:block[1]] if block else None
    return state


def cmd_setup(cdir, args):
    p = paths(cdir)
    if not p["config"].exists():
        p["config"].parent.mkdir(parents=True, exist_ok=True)
        p["config"].write_text("", encoding="utf-8")
    lines = read_lines(p["config"])
    state = load_state(p["state"])
    if not state.get("previous_values"):
        state.update(snapshot_original_state(lines))
        state.setdefault("setup_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    key = resolve_api_key(args)
    backup_now(p["config"], p["models"], p["backup"])
    ensure_deepseek_models(p["models"])

    model_slug = (
        "deepseek-v4-flash" if args.model == "flash" else "deepseek-v4-pro"
    )
    lines = read_lines(p["config"])
    set_top_level(lines, "model", model_slug)
    set_top_level(lines, "model_provider", "deepseek")
    set_top_level(lines, "preferred_auth_method", "apikey")
    set_top_level(lines, "forced_login_method", "api")
    set_top_level(lines, "model_reasoning_effort", "high")
    set_top_level(lines, "model_catalog_json", catalog_value(cdir))
    set_table_field(lines, DEEPSEEK_TABLE, "experimental_bearer_token", key)
    write_lines(p["config"], lines)
    save_state(p["state"], state)

    finish_write(p["config"], p["models"], p["backup"], "DeepSeek 配置完成")
    print("当前模型：%s" % model_slug)
    print("API Key：%s（已安全写入配置）" % mask_key(key))
    print("重要：请重启 ChatGPT（或 Codex）或开新会话后生效。")


def cmd_switch(cdir, args):
    p = paths(cdir)
    if not p["config"].exists():
        sys.exit("config.toml 不存在。请先执行 setup 完成 DeepSeek 首次配置。")
    lines = read_lines(p["config"])

    if args.target == "openai":
        is_deepseek = (
            table_block(lines, DEEPSEEK_TABLE) is not None
            or get_top_level(lines, "model_provider") == "deepseek"
            or (get_top_level(lines, "model") or "").startswith("deepseek-")
        )
        if not is_deepseek:
            print("当前已是 OpenAI 默认配置，无需切换。")
            return
        state = load_state(p["state"])
        if not state.get("previous_values"):
            # No recorded pre-DeepSeek state (e.g. configured by the official
            # script). Remove only values that point at DeepSeek; keep any
            # unrelated user settings intact.
            backup_now(p["config"], p["models"], p["backup"])
            for key in MANAGED_KEYS:
                value = get_top_level(lines, key)
                if value is None:
                    continue
                if key == "model" and not value.startswith("deepseek-"):
                    continue
                if key == "model_provider" and value != "deepseek":
                    continue
                if key == "preferred_auth_method" and value != "apikey":
                    continue
                if key == "forced_login_method" and value != "api":
                    continue
                if key == "model_reasoning_effort" and value != "high":
                    continue
                if key == "model_catalog_json" and value not in (
                    "~/.codex/models.json",
                    str(p["models"]),
                ):
                    continue
                lines = remove_top_level(lines, key)
            lines = remove_table(lines, DEEPSEEK_TABLE)
        else:
            backup_now(p["config"], p["models"], p["backup"])
            for key in MANAGED_KEYS:
                previous = state["previous_values"].get(key)
                if previous is None:
                    lines = remove_top_level(lines, key)
                else:
                    set_top_level(lines, key, previous)
            snapshot = state.get("deepseek_table_snapshot")
            if snapshot:
                lines = replace_table(lines, DEEPSEEK_TABLE, snapshot)
            else:
                lines = remove_table(lines, DEEPSEEK_TABLE)
        write_lines(p["config"], lines)
        finish_write(p["config"], p["models"], p["backup"], "已切回 OpenAI 默认配置")
        print("重要：请重启 ChatGPT（或 Codex）或开新会话后生效。")
        return

    require_deepseek_table(lines)
    model_slug = (
        "deepseek-v4-flash" if args.target == "flash" else "deepseek-v4-pro"
    )
    backup_now(p["config"], p["models"], p["backup"])
    lines = read_lines(p["config"])
    set_top_level(lines, "model", model_slug)
    write_lines(p["config"], lines)
    finish_write(p["config"], p["models"], p["backup"], "模型已切换")
    print("当前模型：%s" % model_slug)
    print("重要：请重启 ChatGPT（或 Codex）或开新会话后生效。")


def cmd_set_key(cdir, args):
    p = paths(cdir)
    if not p["config"].exists():
        sys.exit("config.toml 不存在。请先执行 setup。")
    lines = read_lines(p["config"])
    require_deepseek_table(lines)
    key = resolve_api_key(args)
    backup_now(p["config"], p["models"], p["backup"])
    lines = read_lines(p["config"])
    set_table_field(lines, DEEPSEEK_TABLE, "experimental_bearer_token", key)
    write_lines(p["config"], lines)
    finish_write(p["config"], p["models"], p["backup"], "API Key 已更新")
    print("新 Key：%s（已安全写入配置）" % mask_key(key))
    print("重要：请重启 ChatGPT（或 Codex）或开新会话后生效。")


def cmd_restore(cdir, args):
    p = paths(cdir)
    restored = restore_latest(p["backup"], p["config"], p["models"])
    if not restored:
        sys.exit("没有可恢复的备份。")
    print("[OK] 已从备份恢复：%s" % ", ".join(restored))
    ok, msg = validate_config(p["config"])
    print(("[OK] " if ok else "[WARN] ") + msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="deepseek_switch",
        description="在 Codex 中切换 DeepSeek 模型或切回 OpenAI 默认配置。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="查看当前模型与提供方状态（只读）")

    p_setup = sub.add_parser("setup", help="首次配置 DeepSeek")
    p_setup.add_argument("--model", choices=("flash", "pro"), default="flash")
    p_setup.add_argument("--api-key-stdin", action="store_true")

    p_switch = sub.add_parser("switch", help="切换模型或提供方")
    p_switch.add_argument("target", choices=("flash", "pro", "openai"))

    p_set_key = sub.add_parser("set-key", help="重新设置 DeepSeek API Key")
    p_set_key.add_argument("--api-key-stdin", action="store_true")

    p_restore = sub.add_parser("restore", help="从备份恢复最近一次改动")
    p_restore.add_argument("--latest", action="store_true")

    args = parser.parse_args(argv)
    cdir = config_dir()
    p = paths(cdir)

    if args.command == "status":
        cmd_status(cdir)
    elif args.command == "setup":
        cmd_setup(cdir, args)
    elif args.command == "switch":
        cmd_switch(cdir, args)
    elif args.command == "set-key":
        cmd_set_key(cdir, args)
    elif args.command == "restore":
        cmd_restore(cdir, args)


if __name__ == "__main__":
    main()
