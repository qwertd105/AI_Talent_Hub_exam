import dataclasses

from fastapi.testclient import TestClient

from app.main import build_app
from conftest import wait_done


def test_unavailable_llm_degrades_to_a_human_instead_of_failing(cfg):
    broken = dataclasses.replace(cfg, llm_provider="ollama",
                                 llm_base_url="http://127.0.0.1:9", llm_timeout_s=0.5)
    with TestClient(build_app(broken)) as client:
        response = client.post("/v1/events", json={"text": "Как выгрузить отчёт? Где найти аналитику?"})
        assert response.status_code == 200, "быстрый путь не зависит от внешнего API"
        body = response.json()

        task = wait_done(client, body["task_id"])
        assert task["status"] == "done"
        assert task["result"]["degraded"] is True
        assert task["result"]["decision"] == "review"
        assert task["result"]["review_id"]
        assert client.get("/v1/review").json()["pending"]
        assert client.get("/metrics").json()["degraded"] == 1
