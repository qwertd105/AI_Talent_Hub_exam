"""Сценарии, специфичные для кейса: нормализация каналов и режим suggest."""
from conftest import wait_done


def test_email_is_normalised_and_answered_like_a_chat_message(client):
    """Email приходит темой и телом, чат — одним полем. Дальше по системе идёт
    одно и то же обращение: это и есть работа channel adapters."""
    response = client.post("/v1/events", json={
        "channel": "email",
        "subject": "Как выгрузить отчёт?",
        "body": "Не могу найти, где найти аналитику. Пишите на ivan@example.com",
    })
    body = response.json()
    assert body["decision"] == "auto"
    assert body["label"] == "howto"
    assert "EMAIL" in body["pii_masked"]
    assert "ivan@example.com" not in body["payload_masked"]["body"]

    task = wait_done(client, body["task_id"])
    assert task["status"] == "done"
    assert "KB-101" in task["result"]["answer"]


def test_confident_but_unsafe_category_becomes_a_draft_for_the_operator(client):
    """Уверенность выше порога, но категория закрыта для автоответа: пользователю
    ничего не уходит, оператор получает черновик. Это четвёртое решение роутера."""
    body = client.post("/v1/events", json={
        "text": "Это отвратительно, я крайне недоволен, жалоба на оператора",
    }).json()
    assert body["confidence"] >= 0.9
    assert body["decision"] == "suggest"
    assert "закрыта для автоответа" in body["reason"]
    assert body["review_id"]

    pending = client.get("/v1/review").json()["pending"]
    assert [row["id"] for row in pending] == [body["review_id"]]
    assert client.get("/metrics").json()["suggest"] == 1
