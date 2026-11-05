"""Optional AI study-question drafts via any OpenAI-compatible endpoint.

Works with Ollama, LM Studio, llama.cpp server, OpenAI, and friends.
Opt-in only: nothing here runs unless the user passes --questions.
No API keys are required, stored, or looked for.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "http://127.0.0.1:11434/v1"
DEFAULT_ENDPOINTS = {
    "ollama": "http://127.0.0.1:11434/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "llamacpp": "http://127.0.0.1:8080/v1",
    "openai": "https://api.openai.com/v1",
}
DEFAULT_MODEL = "llama3.2"
TIMEOUT_SECONDS = 30

PROMPT_TEMPLATE = (
    "Write 2 short study questions a beginner could use to test their "
    "recall of this outline branch. Plain language, one line each, no "
    'numbering. Branch: "{branch}" which sits under "{parent}"'
)


def chat_completion(endpoint: str, model: str, messages: list,
                    timeout: float = TIMEOUT_SECONDS) -> str:
    """POST a chat completion request (no authentication headers)."""
    url = endpoint.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(
            f"Endpoint {endpoint} returned HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach {endpoint}: {exc}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected response shape: {data}") from exc


def study_questions(text: str, parent: str, endpoint: str,
                    model: str, timeout: float = TIMEOUT_SECONDS) -> list:
    """Return study-question lines for one branch label."""
    prompt = PROMPT_TEMPLATE.format(branch=text, parent=parent or "the map root")
    content = chat_completion(
        endpoint, model,
        messages=[
            {"role": "system",
             "content": "You are a helpful tutor. Be concise and plain-spoken."},
            {"role": "user", "content": prompt},
        ],
        timeout=timeout,
    )
    questions = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        for prefix in ("- ", "* ", "1. ", "2. ", "3. "):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
        if line:
            questions.append(line)
    return questions


def annotate_questions(root, endpoint: str, model: str,
                       timeout: float = TIMEOUT_SECONDS,
                       only_depth: int | None = 1) -> dict:
    """Build {branch text: [questions]} for top-level branches (or all)."""
    questions: dict = {}
    if root is None or not root.children:
        return questions
    unknown_endpoint = endpoint.strip().lower()
    for preset, url in DEFAULT_ENDPOINTS.items():
        if unknown_endpoint == preset:
            endpoint = url
    for branch in root.children:
        if only_depth is not None and branch.depth > only_depth:
            continue
        try:
            questions[branch.text] = study_questions(
                branch.text, root.text, endpoint, model, timeout)
        except RuntimeError as exc:
            questions[branch.text] = [f"(skipped: {exc})"]
    return questions
