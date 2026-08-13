"""LLM client wrapper (OpenAI-compatible: DeepSeek / DashScope).

The `openai` SDK is imported lazily so tests using FakeLLM never require it.
Per project rule 5, the LLM is used only for judgment (routing, reasoning, aggregation) -
never for deterministic transforms like dependency detection.
"""
import json


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def chat(self, messages: list, **kwargs) -> str:
        from openai import OpenAI  # lazy import
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        # 8192 = DeepSeek's max output tokens (default 4096 truncates long answers).
        resp = client.chat.completions.create(model=self.model, messages=messages,
                                              max_tokens=8192, **kwargs)
        return resp.choices[0].message.content

    def chat_json(self, messages: list) -> dict:
        """LLM output parsed as JSON (for structured ReAct decisions).

        JSON output mode constrains the model to valid JSON at the source
        (supported by DeepSeek; the prompts already contain the required word
        "json"). Fallbacks: complete a JSON structure the model stopped writing
        mid-way, then one retry with the parse error fed back.
        """
        kwargs = {"response_format": {"type": "json_object"}}
        raw = self.chat(messages, **kwargs)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            repaired = self._repair_truncated_json(raw)
            if repaired is not None:
                return json.loads(repaired)
            retry = messages + [{"role": "user", "content": (
                f"Your previous response failed JSON parsing - it may have been "
                f"truncated by the output limit ({e}). "
                "Reply with a shorter valid JSON object: keep 'thought' under "
                "100 characters and 'answer' concise.")}]
            return json.loads(self.chat(retry, **kwargs))

    @staticmethod
    def _repair_truncated_json(raw: str) -> str | None:
        """Models sometimes stop mid-JSON, leaving braces unclosed. Completing the
        envelope is deterministic; return None if the content is broken otherwise."""
        for suffix in ("}", "}}", "}}}"):
            candidate = raw + suffix
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
        return None
