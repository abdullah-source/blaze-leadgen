"""One small LLM client with three backends and a committed response cache.

Backend order (first available wins, or force with LLM_BACKEND=anthropic|claude-cli|cache):
  1. anthropic   ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN present -> Anthropic Messages API
                 with a JSON-schema structured output (model: $LLM_MODEL, default claude-opus-5-5)
  2. claude-cli  `claude` (Claude Code CLI) on PATH -> `claude -p` headless, JSON output,
                 tools disabled. Uses the user's Claude subscription; no API key needed.
  3. cache       no live backend -> only answers already in data/cache/llm_cache.jsonl

Every answer is cached by sha256(system + user). The cache is committed, so a reviewer
can rebuild the final CSV byte-for-byte with zero keys; delete a line (or the file) to
regenerate that lead live.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "cache" / "llm_cache.jsonl"

OUTREACH_SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}, "opener": {"type": "string"}},
    "required": ["subject", "opener"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    pass


def _detect_backend() -> str:
    forced = os.environ.get("LLM_BACKEND")
    if forced:
        return forced
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    if shutil.which("claude"):
        return "claude-cli"
    return "cache"


class LLM:
    def __init__(self, cache_path: Path = CACHE_PATH, backend: str | None = None):
        self.backend = backend or _detect_backend()
        self.model = os.environ.get("LLM_MODEL", "claude-opus-5-5")
        self.cli_model = os.environ.get("CLAUDE_CLI_MODEL", "sonnet")
        self.cache_path = cache_path
        self.cache: dict[str, dict] = {}
        self.calls = 0
        self.cache_hits = 0
        self.cost_usd = 0.0
        self._lock = threading.Lock()
        self._load_cache()
        self._client = None
        if self.backend == "anthropic":
            import anthropic  # imported lazily so the CLI path needs no SDK
            self._client = anthropic.Anthropic()

    # ---------- cache ----------
    def _load_cache(self) -> None:
        if self.cache_path.exists():
            for line in self.cache_path.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.cache[rec["key"]] = rec

    def _store(self, key: str, response: dict, meta: dict) -> None:
        rec = {"key": key, "response": response, **meta}
        with self._lock:
            self.cache[key] = rec
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @staticmethod
    def _key(system: str, user: str) -> str:
        return hashlib.sha256((system + "\n---\n" + user).encode()).hexdigest()

    # ---------- public ----------
    def complete_json(self, system: str, user: str, schema: dict = OUTREACH_SCHEMA) -> tuple[dict, dict]:
        """Return (parsed_json, meta). meta has backend/model/cached/cost_usd."""
        key = self._key(system, user)
        if key in self.cache:
            self.cache_hits += 1
            rec = self.cache[key]
            return rec["response"], {"backend": rec.get("backend"), "model": rec.get("model"), "cached": True, "cost_usd": 0.0}
        if self.backend == "cache":
            raise LLMError("No live LLM backend (set ANTHROPIC_API_KEY or install the claude CLI) and no cached answer for this lead.")
        self.calls += 1
        if self.backend == "anthropic":
            data, meta = self._anthropic(system, user, schema)
        elif self.backend == "claude-cli":
            data, meta = self._claude_cli(system, user, schema)
        else:
            raise LLMError(f"Unknown backend {self.backend}")
        self._validate(data, schema)
        self.cost_usd += meta.get("cost_usd", 0.0) or 0.0
        self._store(key, data, meta)
        return data, {**meta, "cached": False}

    # ---------- backends ----------
    def _anthropic(self, system: str, user: str, schema: dict) -> tuple[dict, dict]:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if resp.stop_reason == "refusal":
            raise LLMError(f"Model refused: {getattr(resp, 'stop_details', None)}")
        text = next(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        return json.loads(text), {
            "backend": "anthropic", "model": resp.model,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "cost_usd": None,
        }

    def _claude_cli(self, system: str, user: str, schema: dict) -> tuple[dict, dict]:
        prompt = (
            user
            + "\n\nRespond with a single JSON object matching this JSON schema and nothing else "
            + "(no markdown fences, no commentary):\n"
            + json.dumps(schema)
        )
        cmd = [
            "claude", "-p", prompt,
            "--model", self.cli_model,
            "--output-format", "json",
            "--system-prompt", system,
            "--tools", "",
            "--no-session-persistence",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(ROOT))
        if proc.returncode != 0:
            raise LLMError(f"claude -p failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise LLMError(f"claude -p returned non-JSON envelope: {proc.stdout[:200]}") from e
        if envelope.get("is_error"):
            raise LLMError(f"claude -p error: {envelope.get('result')}")
        result = envelope.get("result", "")
        data = _extract_json_object(result)
        model = next(iter((envelope.get("modelUsage") or {}).keys()), self.cli_model)
        return data, {"backend": "claude-cli", "model": model, "cost_usd": envelope.get("total_cost_usd")}

    @staticmethod
    def _validate(data: dict, schema: dict) -> None:
        missing = [k for k in schema.get("required", []) if k not in data]
        if missing:
            raise LLMError(f"LLM JSON missing keys: {missing}")
        for k, v in data.items():
            if schema["properties"].get(k, {}).get("type") == "string" and not isinstance(v, str):
                raise LLMError(f"LLM JSON key {k} is not a string")


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise LLMError(f"No JSON object in LLM output: {text[:200]}")
    return json.loads(m.group(0))
