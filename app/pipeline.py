"""Оркестрация: быстрый путь → маскирование → маршрутизация → аудит → (медленный путь).
Не знает о HTTP: то же самое работает из очереди, из скрипта и из теста."""
import json
import uuid

from . import router
from .config import Config
from .domain.base import Domain
from .llm import LLMClient, LLMUnavailable
from .router import Decision
from .safety import detect_injection
from .store import Store


def new_metrics() -> dict[str, int]:
    return {"events": 0, "auto": 0, "suggest": 0, "review": 0, "reject": 0, "degraded": 0}


def as_text(payload: dict) -> str:
    """Человекочитаемое представление события для аудита и для оператора:
    форма события доменная, поэтому единственный универсальный вид — JSON."""
    return json.dumps(payload, ensure_ascii=False)


class Pipeline:
    def __init__(self, cfg: Config, store: Store, domain: Domain, llm: LLMClient,
                 metrics: dict[str, int] | None = None) -> None:
        self.cfg = cfg
        self.store = store
        self.domain = domain
        self.llm = llm
        self.metrics = metrics if metrics is not None else new_metrics()

    def handle(self, payload: dict) -> dict:
        """Быстрый путь. Целевая латентность — десятки миллисекунд, без внешних вызовов."""
        request_id = payload.get("request_id") or uuid.uuid4().hex[:12]
        masked_payload, pii = self.domain.redact(payload)
        masked = as_text(masked_payload)
        injection = detect_injection(
            " ".join(v for v in masked_payload.values() if isinstance(v, str))
        )

        label, confidence = self.domain.fast_path(payload)
        irreversible = self.domain.is_irreversible(payload, label)
        # Домен может не различать «безопасно для автоответа» и «уверенно»; тогда
        # разрешено всё, что прошло порог, и решения suggest не возникает.
        auto_allowed = getattr(self.domain, "auto_allowed", None)
        decision, reason = router.route(
            confidence, self.cfg, irreversible=irreversible,
            auto_allowed=True if auto_allowed is None else auto_allowed(payload, label),
        )
        if injection and decision is Decision.AUTO:
            decision, reason = Decision.REVIEW, "обнаружены признаки prompt injection"

        result = {
            "request_id": request_id,
            "label": label,
            "confidence": round(confidence, 3),
            "decision": decision.value,
            "reason": reason,
            "pii_masked": pii,
            "injection_markers": injection,
            "payload_masked": masked_payload,
            "model_version": self.domain.model_version,
            "answer": None,
            "task_id": None,
            "review_id": None,
            "degraded": False,
        }
        self.store.log_decision(
            request_id=request_id, actor="model", decision=decision.value,
            confidence=confidence, threshold=self.cfg.auto_threshold, reason=reason,
            model_version=self.domain.model_version, payload_masked=masked,
        )
        self.metrics["events"] += 1
        self.metrics[decision.value] += 1
        if decision is not Decision.AUTO:
            result["review_id"] = self.store.enqueue_review(request_id, masked, reason)
        return result

    def generate(self, payload: dict, result: dict) -> dict:
        """Медленный путь: вызывается воркером. В модель уходит только очищенное событие."""
        try:
            context = self.domain.retrieve(payload, result["label"])
            result["answer"] = self.llm.complete(self.domain.build_prompt(payload, context))
            result["degraded"] = False
        except LLMUnavailable as exc:
            previous = result["decision"]
            result["answer"] = None
            result["degraded"] = True
            result["decision"] = Decision.REVIEW.value
            result["reason"] = f"генерация недоступна ({exc}) — обращение передано оператору"
            result["review_id"] = self.store.enqueue_review(
                result["request_id"], as_text(result["payload_masked"]), result["reason"]
            )
            self.store.log_decision(
                request_id=result["request_id"], actor="system", decision=Decision.REVIEW.value,
                confidence=result["confidence"], threshold=self.cfg.auto_threshold,
                reason=result["reason"], model_version=self.domain.model_version,
                payload_masked=as_text(result["payload_masked"]),
            )
            self.metrics["degraded"] += 1
            # решение переехало в review — счётчики обязаны сойтись с очередью
            self.metrics[previous] -= 1
            self.metrics["review"] += 1
        return result
