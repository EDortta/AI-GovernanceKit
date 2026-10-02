from __future__ import annotations

import importlib.util
from pathlib import Path

from governancekit.llm_test import LlmTestResult


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts/test-llm-providers.py"
    spec = importlib.util.spec_from_file_location("test_llm_providers_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_category_distinguishes_authentication_and_endpoint_model() -> None:
    module = _load_script()

    assert module._category("HTTP 401: provider rejected credential") == "authentication"
    assert module._category("HTTP 403: forbidden") == "authentication"
    assert module._category("HTTP 404: provider endpoint or model was not found") == "endpoint-or-model"
    assert module._category("HTTP 410: gone") == "endpoint-or-model"


def test_render_group_marks_failures_and_keeps_passes_clear() -> None:
    module = _load_script()
    lines = module._render_group(
        "TEST",
        [
            LlmTestResult("openai", "gpt", True, "reachable"),
            LlmTestResult("gemini", "flash", False, "HTTP 401"),
        ],
    )
    rendered = "\n".join(lines)

    assert "PASS openai / gpt: reachable" in rendered
    assert "FAIL gemini / flash [authentication]: HTTP 401" in rendered
