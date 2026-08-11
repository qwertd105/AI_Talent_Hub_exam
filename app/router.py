"""Единственное место, где число превращается в решение.

Намеренно без ML: решение «отвечать самому или позвать человека» должно быть
объяснимым построчно и меняться правкой переменной окружения, а не переобучением.
Порядок проверок — часть контракта: необратимость раньше уверенности.
"""
from enum import Enum

from .config import Config


class Decision(str, Enum):
    AUTO = "auto"        # уверенно и безопасно — ответ уходит пользователю
    SUGGEST = "suggest"  # уверенно, но категория требует человека — черновик оператору
    REVIEW = "review"    # риск или серая зона — решает оператор
    REJECT = "reject"    # непонятно, о чём обращение — оператор без черновика


def route(confidence: float, cfg: Config, *, irreversible: bool = False,
          auto_allowed: bool = True) -> tuple[Decision, str]:
    """Возвращает решение и его причину. Причина уходит в аудит дословно."""
    if irreversible:
        return Decision.REVIEW, "необратимое действие — решение принимает человек"
    if confidence >= cfg.auto_threshold:
        if not auto_allowed:
            return Decision.SUGGEST, (
                f"уверенность {confidence:.2f} >= порога авто {cfg.auto_threshold}, "
                "но категория закрыта для автоответа — черновик оператору"
            )
        return Decision.AUTO, f"уверенность {confidence:.2f} >= порога авто {cfg.auto_threshold}"
    if confidence >= cfg.review_threshold:
        return Decision.REVIEW, (
            f"уверенность {confidence:.2f} в серой зоне "
            f"[{cfg.review_threshold}, {cfg.auto_threshold})"
        )
    return Decision.REJECT, f"уверенность {confidence:.2f} < порога ревью {cfg.review_threshold}"
