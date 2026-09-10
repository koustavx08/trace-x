"""Tests for AI provider response parsing and degraded-state reporting.

The providers deliberately fall back to a template when a live call fails, so
an investigator still gets an answer built from real evidence. The risk that
creates is a deployment that has silently stopped calling its model while
still describing itself as live -- which is exactly what a retired model id
produced. These tests pin both halves: the parsing that stops avoidable
failures, and the reporting that makes an unavoidable one visible.
"""

from src.ai.providers.deterministic_demo import DeterministicDemoProvider
from src.ai.providers.openrouter import OpenRouterProvider, _message_text


class _Provider(OpenRouterProvider):
    """An OpenRouter provider with no credentials, for parsing tests only."""

    def __init__(self):
        super().__init__(api_key=None, base_url="https://example.invalid", model=None)


def _completion(content):
    return {"choices": [{"message": {"content": content}}]}


def test_message_text_reads_a_plain_string():
    assert _message_text(_completion("  an answer  ")) == "an answer"


def test_message_text_survives_null_content():
    """A model answering from a reasoning block returns content: null.

    Indexing straight into `.strip()` raised AttributeError, which the caller
    swallowed into a template answer -- a live model reported as working while
    none of its output was ever used.
    """
    assert _message_text(_completion(None)) == ""


def test_message_text_joins_structured_content_parts():
    parts = [{"type": "text", "text": "first "}, {"type": "text", "text": "second"}]
    assert _message_text(_completion(parts)) == "first second"


def test_message_text_falls_back_to_reasoning():
    data = {"choices": [{"message": {"content": None, "reasoning": "the answer"}}]}
    assert _message_text(data) == "the answer"


def test_message_text_handles_an_empty_response():
    assert _message_text({}) == ""
    assert _message_text({"choices": []}) == ""


def test_provider_starts_undegraded():
    provider = _Provider()
    assert provider.degraded is False
    assert provider.last_error is None


def test_failure_is_recorded_with_its_type():
    provider = _Provider()
    provider._record_failure(ValueError("model not found"))
    assert provider.degraded is True
    assert "ValueError" in provider.last_error
    assert "model not found" in provider.last_error


def test_success_clears_a_previous_failure():
    provider = _Provider()
    provider._record_failure(RuntimeError("timeout"))
    provider._record_success()
    assert provider.degraded is False
    assert provider.last_error is None


def test_template_provider_is_never_degraded():
    """The template provider makes no network call, so it cannot degrade."""
    provider = DeterministicDemoProvider()
    assert provider.degraded is False
    assert provider.model_name is None


def test_openrouter_reports_the_model_it_was_configured_with():
    provider = OpenRouterProvider(api_key="test-key", model="anthropic/claude-sonnet-5")
    assert provider.model_name == "anthropic/claude-sonnet-5"
    assert provider.provider_name == "openrouter"
