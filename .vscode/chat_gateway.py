"""Local OpenAI-compatible Qwen3 -> sanitizer gateway for VS Code chat."""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import litellm
import yaml
from flask import Flask, Response, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".vscode" / "config.yaml"
PORT = 8000
PRIMARY_MODEL = "qwen3-coder"
SANITIZER_MODEL = "vscode-chat"
SANITIZER_PROMPT = (
    "You are the final response formatter for a VS Code coding assistant. "
    "Return only the useful answer in clean Markdown. Remove raw system thoughts, "
    "broken streaming fragments, XML tool wrappers, and duplicated text. Preserve "
    "all code, code fences, commands, file paths, and technical meaning exactly. "
    "Do not mention this sanitization step."
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chat_gateway")
app = Flask(__name__)


def _model_params(model_name: str) -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    for model in config.get("model_list", []):
        if model.get("model_name") == model_name:
            params = dict(model.get("litellm_params") or {})
            params.pop("system_prompt", None)
            return params
    raise RuntimeError(f"Model {model_name!r} is missing from {CONFIG_PATH}")


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    return content or ""


def _primary_text(messages: list[dict[str, Any]], request_body: dict[str, Any]) -> str:
    params = _model_params(PRIMARY_MODEL)
    params.update(
        messages=messages,
        temperature=request_body.get("temperature", params.get("temperature", 0.2)),
        top_p=request_body.get("top_p", params.get("top_p", 0.9)),
        max_tokens=request_body.get("max_tokens"),
        timeout=180,
        stream=False,
    )
    params = {key: value for key, value in params.items() if value is not None}
    response = litellm.completion(**params)
    return _message_content(response.choices[0].message)


def _sanitize_text(raw_text: str, request_body: dict[str, Any]) -> str:
    params = _model_params(SANITIZER_MODEL)
    params.update(
        messages=[
            {"role": "system", "content": SANITIZER_PROMPT},
            {
                "role": "user",
                "content": "Format this completed assistant response:\n\n" + raw_text,
            },
        ],
        temperature=0.1,
        max_tokens=request_body.get("max_tokens"),
        timeout=180,
        stream=False,
    )
    params = {key: value for key, value in params.items() if value is not None}
    response = litellm.completion(**params)
    return _message_content(response.choices[0].message).strip()


def _run_pipeline(body: dict[str, Any]) -> tuple[str, str]:
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty array")
    started = time.perf_counter()
    primary = _primary_text(messages, body)
    if not primary:
        return "", "qwen3-coder"
    try:
        cleaned = _sanitize_text(primary, body)
    except Exception:
        logger.exception("Sanitizer failed; returning the primary Qwen3 response")
        cleaned = primary
    logger.info("Completed Qwen3 -> sanitizer pipeline in %.2fs", time.perf_counter() - started)
    return cleaned or primary, body.get("model") or "vscode-chat"


def _completion_response(text: str, model: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/health")
@app.get("/health/liveliness")
def health() -> tuple[Any, int]:
    return jsonify({"status": "healthy"}), 200


@app.get("/v1/models")
def models() -> tuple[Any, int]:
    now = int(time.time())
    return jsonify(
        {
            "object": "list",
            "data": [
                {"id": "vscode-chat", "object": "model", "created": now, "owned_by": "local"},
                {"id": "qwen3-coder", "object": "model", "created": now, "owned_by": "local"},
            ],
        }
    ), 200


@app.post("/v1/chat/completions")
def chat_completions() -> Response | tuple[Any, int]:
    body = request.get_json(silent=True) or {}
    try:
        text, model = _run_pipeline(body)
    except Exception as exc:
        logger.exception("Chat pipeline failed")
        return jsonify({"error": {"message": str(exc), "type": "gateway_error"}}), 502

    if not body.get("stream"):
        return jsonify(_completion_response(text, model))

    completion_id = "chatcmpl-" + uuid.uuid4().hex

    def events():
        yield "data: " + json.dumps(
            {"id": completion_id, "object": "chat.completion.chunk", "model": model,
             "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
        ) + "\n\n"
        for chunk_start in range(0, len(text), 160):
            yield "data: " + json.dumps(
                {"id": completion_id, "object": "chat.completion.chunk", "model": model,
                 "choices": [{"index": 0, "delta": {"content": text[chunk_start:chunk_start + 160]}, "finish_reason": None}]}
            ) + "\n\n"
        yield "data: " + json.dumps(
            {"id": completion_id, "object": "chat.completion.chunk", "model": model,
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        ) + "\n\n"
        yield "data: [DONE]\n\n"

    return Response(events(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True)
