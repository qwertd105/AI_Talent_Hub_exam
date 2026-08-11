"""Интерфейс домена — единственное, что переписывается под кейс.
Всё остальное в app/ доменно-независимо."""
from typing import Protocol


class Domain(Protocol):
    name: str
    model_version: str

    def redact(self, payload: dict) -> tuple[dict, list[str]]:
        """Очищенное событие и список найденных типов PII. Форму события знает только
        домен: он решает, какие поля чувствительны, а какие уходят дальше как есть."""

    def fast_path(self, payload: dict) -> tuple[str, float]:
        """Быстрый синхронный путь: метка и уверенность. Правила или лёгкая модель."""

    def is_irreversible(self, payload: dict, label: str) -> bool:
        """True, если действие нельзя откатить: тогда решает человек, а не модель."""

    def auto_allowed(self, payload: dict, label: str) -> bool:
        """True, если в этой категории автоответ пользователю разрешён вообще.
        Необязательный метод: без него роутер не выдаёт suggest."""

    def needs_generation(self, payload: dict, label: str) -> bool:
        """True, если нужен медленный путь (генерация или тяжёлый инференс)."""

    def retrieve(self, payload: dict, label: str) -> list[str]:
        """Фрагменты, на которых обязан быть основан ответ. Метка уже принята
        на быстром пути — переклассифицировать событие заново нельзя."""

    def build_prompt(self, payload: dict, context: list[str]) -> str:
        """Промпт с явным разделением инструкций и недоверенных данных."""
