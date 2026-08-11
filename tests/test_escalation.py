def test_irreversible_request_goes_to_a_human_and_is_audited(client):
    response = client.post("/v1/events", json={
        "text": "Хочу возврат денег за подписку, карта 4111 1111 1111 1111"
    })
    body = response.json()
    assert body["decision"] == "review"
    assert body["review_id"]
    assert "CARD" in body["pii_masked"]
    assert "4111" not in body["payload_masked"]["text"]

    pending = client.get("/v1/review").json()["pending"]
    assert [row["id"] for row in pending] == [body["review_id"]]

    resolved = client.post(f"/v1/review/{body['review_id']}", json={
        "verdict": "approved", "reviewer": "operator@support", "comment": "проверил оплату"
    })
    assert resolved.status_code == 200
    assert client.get("/v1/review").json()["pending"] == []

    audit = client.get(f"/v1/audit/{body['request_id']}").json()["decisions"]
    assert [row["actor"] for row in audit] == ["model", "human:operator@support"]


def test_resolved_review_cannot_be_resolved_twice(client):
    body = client.post("/v1/events", json={"text": "хочу возврат денег"}).json()
    payload = {"verdict": "approved", "reviewer": "op", "comment": ""}
    assert client.post(f"/v1/review/{body['review_id']}", json=payload).status_code == 200
    assert client.post(f"/v1/review/{body['review_id']}", json=payload).status_code == 404
