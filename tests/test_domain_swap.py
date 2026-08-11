"""Главное свойство шаблона: под новый кейс переписывается только app/domain/.
Домен с другой формой события (фото повреждений авто вместо текста обращения)
должен работать без единой правки в main.py, pipeline.py и остальном app/."""
import json

from fastapi.testclient import TestClient

from app.main import build_app
from app.safety import mask_pii, wrap_untrusted
from conftest import wait_done

PHONE = "+7 999 123-45-67"


class PhotoDomain:
    """Оценка ущерба по фото: событие — ссылка на снимок, а не текст."""

    name = "photo_claims"
    model_version = "stub-0.1"

    def redact(self, payload: dict) -> tuple[dict, list[str]]:
        masked, found = mask_pii(str(payload.get("comment", "")))
        return {**payload, "comment": masked}, found

    def fast_path(self, payload: dict) -> tuple[str, float]:
        score = float(payload.get("damage_score", 0.0))
        if score >= 0.9:
            return "payout", score
        return "inspect", 0.9

    def is_irreversible(self, payload: dict, label: str) -> bool:
        return label == "payout"

    def needs_generation(self, payload: dict, label: str) -> bool:
        return label == "inspect"

    def retrieve(self, payload: dict, label: str) -> list[str]:
        return [f"снимок {payload['image_url']}, полис {payload['policy_id']}, решение {label}"]

    def build_prompt(self, payload: dict, context: list[str]) -> str:
        return ("Ты — ассистент страхового урегулирования. Отвечай только по данным ниже.\n"
                f"{wrap_untrusted(chr(10).join(context))}\n")


def _client(cfg):
    return TestClient(build_app(cfg, domain=PhotoDomain()))


def test_event_of_another_shape_is_accepted(cfg):
    with _client(cfg) as client:
        response = client.post("/v1/events", json={
            "image_url": "https://cdn.example/claim/1.jpg", "policy_id": 7,
            "damage_score": 0.95, "comment": f"мой телефон {PHONE}",
        })
        assert response.status_code == 200, "форма события задаётся доменом, а не main.py"


def test_irreversible_payout_goes_to_a_human_without_leaking_pii(cfg):
    with _client(cfg) as client:
        body = client.post("/v1/events", json={
            "image_url": "https://cdn.example/claim/1.jpg", "policy_id": 7,
            "damage_score": 0.95, "comment": f"мой телефон {PHONE}",
        }).json()

        assert body["decision"] == "review", "необратимая выплата — решает человек"
        assert body["review_id"]
        assert "PHONE" in body["pii_masked"]

        pending = json.dumps(client.get("/v1/review").json()["pending"], ensure_ascii=False)
        audit = json.dumps(client.get(f"/v1/audit/{body['request_id']}").json(), ensure_ascii=False)
        for dump in (json.dumps(body, ensure_ascii=False), pending, audit):
            assert "999" not in dump, "телефон не должен утечь ни в ответ, ни в аудит, ни в ревью"
        assert "cdn.example" in pending, "оператор должен видеть остальные поля заявки"


def test_domain_specific_fields_and_label_reach_retrieve(cfg):
    with _client(cfg) as client:
        body = client.post("/v1/events", json={
            "image_url": "https://cdn.example/claim/2.jpg", "policy_id": 7,
            "damage_score": 0.4, "comment": f"мой телефон {PHONE}",
        }).json()
        assert body["decision"] == "auto"
        assert body["task_id"]

        task = wait_done(client, body["task_id"])
        assert task["status"] == "done"
        assert task["result"]["task_id"] == body["task_id"]
        answer = task["result"]["answer"]
        assert "claim/2.jpg" in answer, "image_url обязан дойти до retrieve через очередь"
        assert "inspect" in answer, "retrieve получает уже принятую метку, а не классифицирует заново"
        assert "999" not in answer
