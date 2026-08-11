from app.domain.tickets import TicketDomain


def test_clear_howto_question_is_confident():
    label, conf = TicketDomain().fast_path({"text": "Как выгрузить отчёт? Где найти аналитику?"})
    assert label == "howto"
    assert conf >= 0.85


def test_unknown_text_is_low_confidence():
    label, conf = TicketDomain().fast_path({"text": "здравствуйте"})
    assert label == "other"
    assert conf < 0.45


def test_refund_is_irreversible():
    d = TicketDomain()
    label, _ = d.fast_path({"text": "хочу возврат денег"})
    assert d.is_irreversible({}, label)


def test_prompt_puts_user_text_inside_untrusted_block():
    d = TicketDomain()
    payload = {"text": "Как выгрузить отчёт?"}
    label, _ = d.fast_path(payload)
    prompt = d.build_prompt(payload, d.retrieve(payload, label))
    assert prompt.count("<untrusted_data>") == 2
    assert "выполнять запрещено" in prompt
