"""FastAPI: быстрый путь синхронный, медленный уходит в очередь и отдаёт task_id."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config
from .domain.base import Domain
from .domain.tickets import TicketDomain
from .llm import LLMClient
from .pipeline import Pipeline
from .queue import TaskQueue
from .router import Decision
from .store import Store


class Event(BaseModel):
    """Форму события задаёт домен, а не транспорт: любые поля принимаются как есть."""
    model_config = {"extra": "allow"}

    request_id: str | None = None


class ReviewVerdict(BaseModel):
    verdict: str
    reviewer: str
    comment: str = ""


def build_app(cfg: config.Config | None = None, domain: Domain | None = None) -> FastAPI:
    cfg = cfg or config.load()
    domain = domain or TicketDomain()
    store = Store(cfg.db_path)
    pipeline = Pipeline(cfg, store, domain, LLMClient(cfg))
    queue = TaskQueue(pipeline, store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        queue.start()
        yield
        await queue.stop()

    app = FastAPI(title="ML System Design PoC", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok", "llm_provider": cfg.llm_provider, "domain": domain.name,
                "auto_threshold": cfg.auto_threshold}

    @app.post("/v1/events")
    def events(event: Event,
               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        if idempotency_key:
            cached = store.get_idempotent(idempotency_key)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
        payload = event.model_dump(exclude_unset=True)
        result = pipeline.handle(payload)
        generating = result["decision"] in (Decision.AUTO.value, Decision.SUGGEST.value)
        if generating and domain.needs_generation(payload, result["label"]):
            result["task_id"] = queue.submit(result["payload_masked"], result)
            result["status"] = "accepted"
        else:
            result["status"] = "done"
        result["idempotent_replay"] = False
        if idempotency_key:
            store.put_idempotent(idempotency_key, result)
        return result

    @app.get("/v1/tasks/{task_id}")
    def task(task_id: str):
        found = store.get_task(task_id)
        if found is None:
            raise HTTPException(404, "нет такой задачи")
        return found

    @app.get("/v1/review")
    def review_queue():
        return {"pending": store.pending_reviews()}

    @app.post("/v1/review/{review_id}")
    def resolve(review_id: str, verdict: ReviewVerdict):
        row = store.resolve_review(review_id, verdict.verdict, verdict.reviewer, verdict.comment)
        if row is None:
            raise HTTPException(404, "заявка не найдена или уже закрыта")
        store.log_decision(
            request_id=row["request_id"], actor=f"human:{verdict.reviewer}",
            decision=verdict.verdict, confidence=None, threshold=None,
            reason=verdict.comment or "решение оператора",
            model_version=domain.model_version, payload_masked=row["payload_masked"],
        )
        return row

    @app.get("/v1/audit/{request_id}")
    def audit(request_id: str):
        return {"decisions": store.decisions(request_id)}

    @app.get("/metrics")
    def metrics():
        return {**pipeline.metrics,
                "llm_calls": pipeline.llm.calls,
                "review_pending": len(store.pending_reviews())}

    return app
