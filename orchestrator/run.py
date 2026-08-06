#!/usr/bin/env python3
"""Minimal OpenAI-compatible orchestrator harness.

This file intentionally contains no secrets. Configure with `.env` or process
environment variables.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


def vault_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_registry() -> tuple[dict[str, list[tuple[int, str]]], list[tuple[int, str]]]:
    exact: dict[str, list[tuple[int, str]]] = {}
    wildcard: list[tuple[int, str]] = []

    pattern = re.compile(r"^LLM_KEY_(\d+)$")
    entries: list[tuple[int, str]] = []
    for env_key, api_key in os.environ.items():
        match = pattern.match(env_key)
        if not match or not api_key:
            continue

        entries.append((int(match.group(1)), api_key))

    for index, api_key in sorted(entries, key=lambda item: item[0]):
        models_raw = os.environ.get(f"LLM_KEY_{index}_MODELS", "")
        models = [model.strip() for model in models_raw.split(",") if model.strip()]
        for model in models:
            lowered = model.lower()
            if lowered in {"*", "all", "all models", "wildcard"} or "all " in lowered:
                wildcard.append((index, api_key))
            else:
                exact.setdefault(model, []).append((index, api_key))

    legacy = os.environ.get("ORCHESTRATOR_API_KEY")
    if legacy and not exact and not wildcard:
        wildcard.append((0, legacy))

    for matches in exact.values():
        matches.sort(key=lambda item: item[0])
    wildcard.sort(key=lambda item: item[0])

    return exact, wildcard


def rotation_state_path() -> Path:
    runtime = vault_root() / ".runtime"
    runtime.mkdir(exist_ok=True)
    return runtime / "orchestrator-rotation.json"


def select_key(model: str) -> tuple[int, str]:
    exact, wildcard = parse_registry()
    matches = exact.get(model, [])

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        state_path = rotation_state_path()
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        current = int(state.get(model, -1))
        next_position = (current + 1) % len(matches)
        state[model] = next_position
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return matches[next_position]

    if wildcard:
        return wildcard[0]

    raise RuntimeError(f"No API key mapping found for requested model: {model}")


def log_key_choice(model: str, key_index: int) -> None:
    log_dir = vault_root() / "05-Logs"
    log_dir.mkdir(exist_ok=True)
    path = log_dir / f"orchestrator-routing-{__import__('datetime').date.today().isoformat()}.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{model} → LLM_KEY_{key_index}\n")


def call_model(prompt: str) -> str:
    base_url = os.environ.get("ORCHESTRATOR_BASE_URL", "").rstrip("/")
    model = os.environ.get("ORCHESTRATOR_MODEL", "chatgpt-web")
    if not base_url:
        raise RuntimeError("Missing ORCHESTRATOR_BASE_URL.")

    key_index, api_key = select_key(model)
    log_key_choice(model, key_index)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are the Super-Repo orchestrator. File ambiguities as Open Questions and never expose secrets."},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:1000]
        raise RuntimeError(f"Model call failed with HTTP {exc.code}: {body}") from exc

    return decoded["choices"][0]["message"]["content"]


def main(argv: list[str]) -> int:
    load_dotenv(vault_root() / ".env")
    prompt = " ".join(argv[1:]).strip()
    if not prompt:
        print("usage: run.py <prompt>", file=sys.stderr)
        return 2

    try:
        print(call_model(prompt))
    except Exception as exc:
        print(f"orchestrator error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
