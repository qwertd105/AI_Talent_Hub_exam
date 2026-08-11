from conftest import wait_done


def test_known_question_is_answered_without_a_human(client):
    response = client.post("/v1/events", json={"text": "Как выгрузить отчёт? Где найти аналитику?"})
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "auto"
    assert body["status"] == "accepted"
    assert body["task_id"]

    task = wait_done(client, body["task_id"])
    assert task["status"] == "done"
    assert "Аналитика" in task["result"]["answer"]
    assert task["result"]["degraded"] is False

    assert client.get("/v1/review").json()["pending"] == []
    audit = client.get(f"/v1/audit/{body['request_id']}").json()["decisions"]
    assert [row["actor"] for row in audit] == ["model"]
