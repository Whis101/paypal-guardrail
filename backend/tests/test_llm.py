"""Claude calls, tested against a fake client: no network, no API key, no cost."""

from types import SimpleNamespace

import pytest

from app.llm import (
    DEFAULT_MANDATE,
    MODEL,
    Classification,
    LLMError,
    classify,
    generate_proposal,
)


class FakeMessages:
    def __init__(self, create_result=None, parse_result=None):
        self.create_result = create_result
        self.parse_result = parse_result
        self.calls: list[tuple[str, dict]] = []

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return self.create_result

    def parse(self, **kwargs):
        self.calls.append(("parse", kwargs))
        return self.parse_result


def fake_client(**kw) -> SimpleNamespace:
    return SimpleNamespace(messages=FakeMessages(**kw))


def text_response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
    )


GOOD = Classification(
    merchant="Costco",
    amount_cents=8743,
    category="groceries",
    item_description="Bulk paper towels and coffee",
    confidence=0.92,
)


def test_generate_proposal_returns_text_and_uses_haiku():
    client = fake_client(create_result=text_response("Buy coffee at Costco for $12.99"))
    out = generate_proposal(client, "keep the pantry stocked")
    assert out == "Buy coffee at Costco for $12.99"
    kind, kwargs = client.messages.calls[0]
    assert kind == "create"
    assert kwargs["model"] == MODEL == "claude-haiku-5-5"
    # The mandate is user content, never spliced into the system prompt.
    assert "keep the pantry stocked" in kwargs["messages"][0]["content"]
    assert "keep the pantry stocked" not in kwargs["system"]


def test_generate_proposal_blank_mandate_uses_default():
    client = fake_client(create_result=text_response("x"))
    generate_proposal(client, "   ")
    assert DEFAULT_MANDATE in client.messages.calls[0][1]["messages"][0]["content"]


def test_generate_proposal_rejects_overlong_mandate():
    client = fake_client(create_result=text_response("x"))
    with pytest.raises(LLMError):
        generate_proposal(client, "a" * 2001)
    assert client.messages.calls == []  # never sent


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_generate_proposal_bad_stop_reason_raises(stop):
    client = fake_client(create_result=text_response("partial", stop_reason=stop))
    with pytest.raises(LLMError):
        generate_proposal(client, "x")


def test_generate_proposal_empty_text_raises():
    client = fake_client(create_result=text_response("   "))
    with pytest.raises(LLMError):
        generate_proposal(client, "x")


def test_classify_returns_parsed_output_via_structured_outputs():
    resp = SimpleNamespace(stop_reason="end_turn", parsed_output=GOOD)
    client = fake_client(parse_result=resp)
    out = classify(client, "Buy paper towels at Costco, $87.43")
    assert out == GOOD
    kind, kwargs = client.messages.calls[0]
    assert kind == "parse"
    assert kwargs["output_format"] is Classification
    assert "Costco, $87.43" in kwargs["messages"][0]["content"]


@pytest.mark.parametrize(
    "resp",
    [
        SimpleNamespace(stop_reason="refusal", parsed_output=None),
        SimpleNamespace(stop_reason="end_turn", parsed_output=None),
        SimpleNamespace(stop_reason="max_tokens", parsed_output=GOOD),
    ],
)
def test_classify_failure_modes_raise(resp):
    with pytest.raises(LLMError):
        classify(fake_client(parse_result=resp), "anything")


def test_classification_category_is_a_closed_set():
    with pytest.raises(ValueError):
        Classification(
            merchant="X", amount_cents=1, category="weapons", item_description="", confidence=1
        )
