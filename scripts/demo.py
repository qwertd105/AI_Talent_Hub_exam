"""Прогон обоих сценариев одной командой — для показа на защите.
Печатает решение, причину и состояние очереди ревью."""
import dataclasses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import build_app  # noqa: E402

CASES = [
    ("happy path", {"text": "Как выгрузить отчёт? Где найти аналитику?"}),
    ("рискованный путь", {"text": "Хочу возврат денег, карта 4111 1111 1111 1111"}),
    ("email как канал", {"channel": "email", "subject": "Как выгрузить отчёт?",
                         "body": "Не могу найти, где найти аналитику"}),
    ("suggest: уверенно, но нельзя авто",
     {"text": "Это отвратительно, я крайне недоволен, жалоба на оператора"}),
]


def run(cfg, title):
    print(f"\n=== {title} (провайдер: {cfg.llm_provider}) ===")
    with TestClient(build_app(cfg)) as client:
        for name, payload in CASES:
            body = client.post("/v1/events", json=payload).json()
            print(f"[{name}] решение={body['decision']} уверенность={body['confidence']} "
                  f"причина={body['reason']}")
            print(f"          PII замаскировано: {body['pii_masked'] or 'нет'}")
            if body["task_id"]:
                for _ in range(100):
                    task = client.get(f"/v1/tasks/{body['task_id']}").json()
                    if task["status"] in ("done", "failed"):
                        break
                    time.sleep(0.05)
                print(f"          ответ: {task['result']['answer']}")
                print(f"          деградация: {task['result']['degraded']}")
        print("  очередь ревью:", [r["reason"] for r in client.get("/v1/review").json()["pending"]])
        print("  метрики:", client.get("/metrics").json())


if __name__ == "__main__":
    base = dataclasses.replace(config.load(), db_path="demo.db")
    run(base, "штатная работа")
    run(dataclasses.replace(base, db_path="demo_broken.db", llm_provider="ollama",
                            llm_base_url="http://127.0.0.1:9", llm_timeout_s=0.5),
        "внешний LLM недоступен")
