"""Адаптер к генерации. Провайдер выбирается переменной окружения; stub детерминирован
и работает без сети — он же путь деградации, когда внешний API недоступен."""
import hashlib
import os
import re
import time

import httpx

from .config import Config


class LLMUnavailable(RuntimeError):
    """Генерация недоступна. Вызывающий обязан деградировать, а не падать."""


class Breaker:
    """После N подряд ошибок перестаём ходить в провайдера на cooldown секунд:
    иначе очередь забивается таймаутами и деградирует весь сервис, а не одна ручка."""

    def __init__(self, failures: int, cooldown_s: float) -> None:
        self.limit = failures
        self.cooldown = cooldown_s
        self.failures = 0
        self.opened_at = 0.0

    def is_open(self) -> bool:
        if self.failures < self.limit:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown:
            self.failures = 0
            return False
        return True

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.limit:
            self.opened_at = time.monotonic()

    def record_success(self) -> None:
        self.failures = 0


class LLMClient:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.breaker = Breaker(cfg.breaker_failures, cfg.breaker_cooldown_s)
        self.cache: dict[str, str] = {}
        self.calls = 0

    def complete(self, prompt: str) -> str:
        key = hashlib.sha256(prompt.encode()).hexdigest()
        if key in self.cache:
            return self.cache[key]
        if self.cfg.llm_provider == "stub":
            out = _stub(prompt)
        else:
            if self.breaker.is_open():
                raise LLMUnavailable("circuit breaker открыт")
            try:
                out = self._remote(prompt)
            except Exception as exc:
                self.breaker.record_failure()
                raise LLMUnavailable(str(exc)) from exc
            self.breaker.record_success()
        self.calls += 1
        self.cache[key] = out
        return out

    def _remote(self, prompt: str) -> str:
        cfg = self.cfg
        if cfg.llm_provider == "ollama":
            r = httpx.post(
                f"{cfg.llm_base_url}/api/generate",
                json={"model": cfg.llm_model, "prompt": prompt, "stream": False},
                timeout=cfg.llm_timeout_s,
            )
            r.raise_for_status()
            return r.json()["response"].strip()
        if cfg.llm_provider == "openai":
            r = httpx.post(
                f"{cfg.llm_base_url}/v1/chat/completions",
                json={"model": cfg.llm_model, "messages": [{"role": "user", "content": prompt}]},
                headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY', '')}"},
                timeout=cfg.llm_timeout_s,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        raise LLMUnavailable(f"неизвестный провайдер {cfg.llm_provider}")


def _stub(prompt: str) -> str:
    """Детерминированный ответ, собранный из переданного контекста. Ничего не выдумывает:
    без контекста честно отдаёт обращение оператору — это и есть поведение при отказе."""
    blocks = re.findall(r"<untrusted_data>\n(.*?)\n</untrusted_data>", prompt, re.S)
    if not blocks:
        return "Не нашёл подтверждающих фрагментов в базе знаний. Передаю обращение оператору."
    first = " ".join(blocks[0].split())[:300]
    return f"По документам: {first} (источник: фрагмент 1)"
