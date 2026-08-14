#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$SKILL_DIR/scripts/deepseek_switch.py"
FIXTURES="$SKILL_DIR/tests/fixtures"

run_for() {
  local py="$1"
  local label="$2"
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/.codex"
  cp "$FIXTURES/config.toml" "$tmp/.codex/config.toml"
  cp "$FIXTURES/models.json" "$tmp/.codex/models.json"
  export CODEX_HOME="$tmp/.codex"

  echo "===== $label ====="

  DEEPSEEK_API_KEY=sk-test-123456 "$py" "$SCRIPT" setup
  "$py" "$SCRIPT" status | grep -q "deepseek-v4-flash"

  "$py" - <<'EOF'
import json, os
d = json.load(open(os.path.join(os.environ["CODEX_HOME"], "models.json")))
slugs = [m["slug"] for m in d["models"]]
assert "my-existing-model" in slugs, "existing model must be preserved"
assert "deepseek-v4-flash" in slugs and "deepseek-v4-pro" in slugs
print("models.json merge OK")
EOF

  "$py" "$SCRIPT" switch pro
  "$py" "$SCRIPT" status | grep -q "deepseek-v4-pro"

  "$py" "$SCRIPT" switch flash
  "$py" "$SCRIPT" status | grep -q "deepseek-v4-flash"

  DEEPSEEK_API_KEY=sk-new-key-9999 "$py" "$SCRIPT" set-key
  if "$py" "$SCRIPT" status | grep -q "sk-new-key-9999"; then
    echo "FAIL: API key leaked into output"; exit 1
  fi

  "$py" "$SCRIPT" switch openai
  diff "$FIXTURES/config.toml" "$tmp/.codex/config.toml" >/dev/null

  "$py" "$SCRIPT" restore --latest
  "$py" "$SCRIPT" status | grep -q "deepseek-v4-flash"

  rm -rf "$tmp"
  echo "===== $label PASSED ====="
}

run_for python3 "Python 3.8 (fallback validation)"
run_for /Users/bing/.local/bin/python3.11 "Python 3.11 (tomllib validation)"

run_fallback() {
  local py="$1"
  local label="$2"
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/.codex"
  cp "$FIXTURES/config.deepseek.toml" "$tmp/.codex/config.toml"
  cp "$FIXTURES/models.json" "$tmp/.codex/models.json"
  export CODEX_HOME="$tmp/.codex"

  echo "===== $label (official-script style, switch openai) ====="
  "$py" "$SCRIPT" switch openai
  if grep -q "model_providers.deepseek" "$tmp/.codex/config.toml"; then
    echo "FAIL: deepseek table still present"; exit 1
  fi
  if ! grep -q 'trust_level = "trusted"' "$tmp/.codex/config.toml"; then
    echo "FAIL: unrelated config lost"; exit 1
  fi
  "$py" "$SCRIPT" switch openai | grep -q "已是 OpenAI 默认配置"

  rm -rf "$tmp"
  echo "===== $label PASSED ====="
}

run_fallback python3 "Python 3.8"
run_fallback /Users/bing/.local/bin/python3.11 "Python 3.11"
echo "ALL TESTS PASSED"
