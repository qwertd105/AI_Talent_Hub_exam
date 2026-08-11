def test_retry_with_the_same_key_does_not_create_a_second_review(client):
    payload = {"text": "Хочу возврат денег за подписку"}
    headers = {"Idempotency-Key": "retry-1"}
    first = client.post("/v1/events", json=payload, headers=headers).json()
    second = client.post("/v1/events", json=payload, headers=headers).json()

    assert second["idempotent_replay"] is True
    assert second["review_id"] == first["review_id"]
    assert len(client.get("/v1/review").json()["pending"]) == 1


def test_different_keys_are_separate_requests(client):
    payload = {"text": "Хочу возврат денег за подписку"}
    first = client.post("/v1/events", json=payload, headers={"Idempotency-Key": "a"}).json()
    second = client.post("/v1/events", json=payload, headers={"Idempotency-Key": "b"}).json()
    assert first["review_id"] != second["review_id"]
    assert len(client.get("/v1/review").json()["pending"]) == 2
