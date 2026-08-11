import dataclasses

import pytest

from app import config
from app.llm import Breaker, LLMClient, LLMUnavailable


def _cfg(**kw):
    return dataclasses.replace(config.load(), **kw)


def test_stub_is_deterministic_and_grounded():
    client = LLMClient(_cfg(llm_provider="stub"))
    prompt = "инструкции\n<untrusted_data>\nОтчёты лежат в разделе «Аналитика».\n</untrusted_data>"
    first = client.complete(prompt)
    assert "Аналитика" in first
    assert LLMClient(_cfg(llm_provider="stub")).complete(prompt) == first


def test_stub_admits_when_there_is_no_context():
    client = LLMClient(_cfg(llm_provider="stub"))
    assert "оператору" in client.complete("вопрос без контекста")


def test_cache_prevents_second_call():
    client = LLMClient(_cfg(llm_provider="stub"))
    client.complete("одно и то же")
    client.complete("одно и то же")
    assert client.calls == 1


def test_unreachable_provider_raises_llm_unavailable():
    client = LLMClient(_cfg(llm_provider="ollama", llm_base_url="http://127.0.0.1:9", llm_timeout_s=0.5))
    with pytest.raises(LLMUnavailable):
        client.complete("привет")


def test_breaker_opens_and_cools_down():
    b = Breaker(failures=2, cooldown_s=0.2)
    assert not b.is_open()
    b.record_failure()
    b.record_failure()
    assert b.is_open()
    import time
    time.sleep(0.25)
    assert not b.is_open()
