import dataclasses
import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import build_app


@pytest.fixture
def cfg(tmp_path):
    return dataclasses.replace(config.load(), db_path=str(tmp_path / "test.db"),
                               llm_provider="stub")


@pytest.fixture
def client(cfg):
    with TestClient(build_app(cfg)) as c:
        yield c


def wait_done(client, task_id, timeout_s=5.0):
    """Медленный путь асинхронный: ждём терминального статуса, а не спим наугад."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        task = client.get(f"/v1/tasks/{task_id}").json()
        if task["status"] in ("done", "failed"):
            return task
        time.sleep(0.05)
    raise AssertionError(f"задача {task_id} не завершилась за {timeout_s} с")
