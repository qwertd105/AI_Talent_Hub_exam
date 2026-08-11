"""Границы доверия. Ничто не уходит во внешний вызов, не пройдя mask_pii;
никакой текст пользователя не попадает в промпт как инструкция."""
import re

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)")),
    ("PASSPORT", re.compile(r"(?<!\d)\d{4}\s?\d{6}(?!\d)")),
]

INJECTION_MARKERS = [
    "ignore previous",
    "ignore all previous",
    "disregard the above",
    "system prompt",
    "you are now",
    "reveal your",
    "игнорируй предыдущ",
    "забудь инструкции",
    "покажи промпт",
    "ты теперь",
]


def mask_pii(text: str) -> tuple[str, list[str]]:
    """Возвращает текст с заменёнными персональными данными и список найденных типов."""
    found: list[str] = []
    for name, rx in PII_PATTERNS:
        text, n = rx.subn(f"<{name}>", text)
        if n:
            found.append(name)
    return text, found


def detect_injection(text: str) -> list[str]:
    low = text.lower()
    return [m for m in INJECTION_MARKERS if m in low]


def wrap_untrusted(text: str) -> str:
    """Данные — не инструкции. Угловые скобки внутри нейтрализуются,
    чтобы текст пользователя не смог закрыть блок и выйти наружу."""
    safe = text.replace("<", "‹").replace(">", "›")
    return f"<untrusted_data>\n{safe}\n</untrusted_data>"
