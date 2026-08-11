"""Пороги и параметры внешних сервисов. Всё из env: на защите пороги двигают,
не трогая код, — это отдельный аргумент про цену ошибки."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    auto_threshold: float
    review_threshold: float
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_timeout_s: float
    breaker_failures: int
    breaker_cooldown_s: float
    db_path: str


def load() -> Config:
    return Config(
        auto_threshold=float(os.getenv("AUTO_THRESHOLD", "0.9")),
        review_threshold=float(os.getenv("REVIEW_THRESHOLD", "0.45")),
        llm_provider=os.getenv("LLM_PROVIDER", "stub"),
        llm_model=os.getenv("LLM_MODEL", "qwen2.5:3b-instruct"),
        llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "10")),
        breaker_failures=int(os.getenv("BREAKER_FAILURES", "3")),
        breaker_cooldown_s=float(os.getenv("BREAKER_COOLDOWN_S", "30")),
        db_path=os.getenv("DB_PATH", "poc.db"),
    )
