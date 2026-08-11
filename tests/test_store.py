from app.store import Store


def test_audit_keeps_order_and_actor(tmp_path):
    s = Store(str(tmp_path / "a.db"))
    s.log_decision(request_id="r1", actor="model", decision="review", confidence=0.5,
                   threshold=0.85, reason="серая зона", model_version="v1", payload_masked="текст")
    s.log_decision(request_id="r1", actor="human:op", decision="approved", confidence=None,
                   threshold=None, reason="проверил", model_version="v1", payload_masked="текст")
    rows = s.decisions("r1")
    assert [r["actor"] for r in rows] == ["model", "human:op"]
    assert rows[0]["threshold"] == 0.85


def test_idempotency_returns_first_response(tmp_path):
    s = Store(str(tmp_path / "b.db"))
    assert s.get_idempotent("k") is None
    s.put_idempotent("k", {"decision": "auto"})
    s.put_idempotent("k", {"decision": "reject"})
    assert s.get_idempotent("k") == {"decision": "auto"}


def test_review_can_be_resolved_once(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    rid = s.enqueue_review("r2", "текст", "необратимо")
    assert [r["id"] for r in s.pending_reviews()] == [rid]
    row = s.resolve_review(rid, "approved", "op", "ок")
    assert row["status"] == "resolved"
    assert s.pending_reviews() == []
    assert s.resolve_review(rid, "approved", "op", "повтор") is None


def test_task_result_roundtrip(tmp_path):
    s = Store(str(tmp_path / "d.db"))
    s.put_task("t1", "r3", "queued")
    s.put_task("t1", "r3", "done", {"answer": "готово"})
    t = s.get_task("t1")
    assert t["status"] == "done"
    assert t["result"]["answer"] == "готово"
    assert s.get_task("нет") is None
