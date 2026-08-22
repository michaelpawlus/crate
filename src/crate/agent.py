"""LLM agent runtime.

The SOURCE / TRIANGULATE / SEQUENCE stages and feedback parsing are LLM work.
Default backend invokes the Claude Code CLI headlessly (`claude -p`) so a Max
plan covers it with no API key. Set CRATE_AGENT_BACKEND=api (and
ANTHROPIC_API_KEY, plus `pip install crate[api]`) to use the Anthropic API
instead.

Prompts live as versioned Markdown in src/crate/prompts/. The curator mindset
lives in curator-system.md and is prepended to every call.
"""

import hashlib
import json
import os
import re
import subprocess
from importlib import resources
from typing import Any

DEFAULT_TIMEOUT = 900


class AgentError(RuntimeError):
    pass


def load_prompt(name: str, **kwargs: str) -> str:
    text = (resources.files("crate") / "prompts" / f"{name}.md").read_text()
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def system_prompt() -> str:
    return load_prompt("curator-system")


def backend() -> str:
    return os.environ.get("CRATE_AGENT_BACKEND", "claude-cli")


def run_agent(
    prompt: str,
    *,
    web: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Run one agent task and return its text response."""
    if backend() == "api":
        return _run_api(prompt, timeout=timeout)
    return _run_claude_cli(prompt, web=web, timeout=timeout)


def run_agent_json(prompt: str, *, web: bool = False, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """Run one agent task and parse a JSON object/array out of the response."""
    text = run_agent(prompt, web=web, timeout=timeout)
    return extract_json(text)


def _run_claude_cli(prompt: str, *, web: bool, timeout: int) -> str:
    cmd = ["claude", "-p", "--output-format", "json"]
    model = os.environ.get("CRATE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd += ["--append-system-prompt", system_prompt()]
    if web:
        # Restrict the tool set to web research and pre-approve it so the
        # headless run never stalls on a permission prompt.
        cmd += ["--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch", "WebFetch"]
    else:
        cmd += ["--tools", ""]  # pure-text task; no tools needed
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        raise AgentError(
            "`claude` CLI not found. Install Claude Code, or set "
            "CRATE_AGENT_BACKEND=api with an ANTHROPIC_API_KEY."
        ) from None
    except subprocess.TimeoutExpired:
        raise AgentError(f"Agent call timed out after {timeout}s.") from None
    if proc.returncode != 0:
        raise AgentError(f"claude -p failed: {proc.stderr.strip()[:2000]}")
    try:
        payload = json.loads(proc.stdout)
        result = payload.get("result", "")
    except json.JSONDecodeError:
        result = proc.stdout
    if not result:
        raise AgentError("Agent returned an empty response.")
    return result


def _run_api(prompt: str, *, timeout: int) -> str:
    try:
        import anthropic
    except ImportError:
        raise AgentError("Install the API extra: uv sync --extra api") from None
    client = anthropic.Anthropic()
    model = os.environ.get("CRATE_MODEL", "claude-sonnet-5")
    resp = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system_prompt(),
        messages=[{"role": "user", "content": prompt}],
        timeout=timeout,
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def salvage_truncated_json(text: str) -> Any | None:
    """Recover the complete leading part of a JSON value that was cut off
    mid-generation, or None if nothing usable is there.

    A long stage response can stop mid-token when the model runs out of output
    room, and strict parsing then throws away every element that *did* arrive.
    Walks the text tracking string/escape state, remembers the last point where
    a top-level element closed cleanly, and re-closes the containers that were
    still open at that point.

    Safe for every current caller because each one already validates
    completeness downstream: SOURCE requires a minimum candidate count,
    TRIANGULATE requires enough judged tracks, and SEQUENCE appends anything the
    order omitted. A short list gets caught there rather than passing silently.
    """
    stack: list[str] = []
    closer_for = {"{": "}", "[": "]"}
    in_string = False
    escaped = False
    start = -1
    last_good = -1

    for i, ch in enumerate(text):
        if start == -1:
            if ch in "{[":
                start = i
                stack.append(ch)
            continue
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack or closer_for[stack[-1]] != ch:
                break
            stack.pop()
            if not stack:
                last_good = i  # a complete top-level value
                break
            if len(stack) <= 2:
                # An element of the outer container (or of its first array)
                # finished here; this is a safe truncation point.
                last_good = i

    if start == -1 or last_good == -1:
        return None

    head = text[start : last_good + 1].rstrip().rstrip(",")
    in_string = False
    escaped = False
    open_stack: list[str] = []
    for ch in head:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            open_stack.append(ch)
        elif ch in "}]" and open_stack:
            open_stack.pop()

    repaired = head + "".join(closer_for[c] for c in reversed(open_stack))
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _dump_failure(text: str) -> str | None:
    """Write an unparseable response to disk so it can be diagnosed.

    The exception message truncates at 1000 characters, which is not enough to
    tell a cut-off response from a malformed one - exactly the question that
    matters when a stage fails.
    """
    try:
        from . import config, state

        path = (
            config.cache_dir()
            / "agent-failures"
            / f"{state.today_stamp()}-{hashlib.sha256(text.encode()).hexdigest()[:8]}.txt"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return str(path)
    except OSError:
        return None


def extract_json(text: str) -> Any:
    """Pull the first JSON object or array out of agent output, tolerating
    prose and code fences around it, and recovering the complete leading part of
    a response that was cut off mid-generation."""
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    candidates = [*fenced, text]
    for candidate in candidates:
        candidate = candidate.strip()
        # Try the outermost structure first: whichever bracket opens earliest.
        pairs = sorted(
            (("[", "]"), ("{", "}")),
            key=lambda p: (candidate.find(p[0]) == -1, candidate.find(p[0])),
        )
        for opener, closer in pairs:
            start = candidate.find(opener)
            if start == -1:
                continue
            end = candidate.rfind(closer)
            if end <= start:
                continue
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue

    for candidate in candidates:
        recovered = salvage_truncated_json(candidate.strip())
        if recovered is not None:
            return recovered

    dumped = _dump_failure(text)
    where = f"\nFull response written to {dumped}" if dumped else ""
    raise AgentError(
        f"Could not parse JSON from agent response:\n{text[:1000]}{where}"
    )


def agent_available() -> tuple[bool, str]:
    """For `crate doctor`: report which backend is usable."""
    if backend() == "api":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return True, "anthropic API (ANTHROPIC_API_KEY set)"
        return False, "CRATE_AGENT_BACKEND=api but ANTHROPIC_API_KEY is not set"
    try:
        proc = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=30
        )
        return True, f"claude CLI ({proc.stdout.strip()})"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "`claude` CLI not found on PATH"
