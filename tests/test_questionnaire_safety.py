from harvis.features import questionnaire


def test_questionnaire_fills_visible_answers_but_never_submits(monkeypatch) -> None:
    monkeypatch.setattr(
        questionnaire,
        "inspect_visible_questionnaire",
        lambda: {
            "capture": {
                "origin_x": 0,
                "origin_y": 0,
                "width": 1000,
                "height": 800,
            },
            "questions": [
                {
                    "question": "2 + 2?",
                    "answer": "4",
                    "control": "choice",
                    "target": "answer option 4",
                    "target_point_2d": [250, 500],
                    "confidence": 0.99,
                },
                {
                    "question": "Name a color",
                    "answer": "Blue",
                    "control": "text",
                    "target": "text field under Name a color",
                    "target_point_2d": [500, 500],
                    "confidence": 0.9,
                },
                {
                    "question": "Finish",
                    "answer": "Submit",
                    "control": "choice",
                    "target": "Submit answers button",
                    "target_point_2d": [750, 500],
                    "confidence": 1.0,
                },
            ]
        },
    )
    calls: list[tuple[str, dict]] = []

    def executor(name, arguments):
        calls.append((name, arguments))
        return {
            "status": "clicked" if name == "click_questionnaire_point" else "completed"
        }

    result = questionnaire.complete_visible_questionnaire(executor)

    assert result["filled"] == 2
    assert result["submitted"] is False
    assert (
        "type_text_unwatermarked",
        {"text": "Blue"},
    ) in calls
    assert not any(name == "vision_click" for name, _ in calls)
    click_calls = [
        arguments
        for name, arguments in calls
        if name == "click_questionnaire_point"
    ]
    assert [call["y"] for call in click_calls] == [400, 200]
    assert not any("submit" in str(arguments).casefold() for _, arguments in calls)


def test_chatgpt_result_parser_uses_bounded_structured_block() -> None:
    text = """
HARVIS_QUIZ_RESULT
Q: Capital of Costa Rica?
TYPE: choice
A: San José
Q: Explain briefly
TYPE: text
A: A short answer
END_HARVIS_QUIZ_RESULT
"""

    result = questionnaire._parse_chatgpt_answers(text)

    assert result == [
        {"question": "Capital of Costa Rica?", "control": "choice", "answer": "San José"},
        {"question": "Explain briefly", "control": "text", "answer": "A short answer"},
    ]


def test_chatgpt_fallback_detects_sensitive_fields() -> None:
    assert questionnaire._contains_sensitive_fallback_text(
        "Account password: do not share"
    )
    assert not questionnaire._contains_sensitive_fallback_text(
        "What is the capital of Costa Rica?"
    )
    assert not questionnaire._contains_sensitive_fallback_text(
        "Menciona una práctica recomendada para crear contraseñas seguras."
    )


def test_quota_fallback_opens_temporary_chat_for_educational_password_question(
    monkeypatch,
) -> None:
    opened: list[str] = []
    typed: list[str] = []

    monkeypatch.setattr(questionnaire.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        questionnaire,
        "_copy_active_window_text",
        lambda **kwargs: (
            "11. Menciona una práctica recomendada para crear contraseñas seguras.\n"
            "Respuesta:\n"
        ),
    )
    monkeypatch.setattr(questionnaire, "open_default_browser", opened.append)
    monkeypatch.setattr(
        questionnaire,
        "type_text",
        lambda text, **kwargs: typed.append(text) or {"status": "completed"},
    )
    monkeypatch.setattr(
        questionnaire,
        "press_key",
        lambda *args, **kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(questionnaire.time, "sleep", lambda _: None)
    monkeypatch.setattr(questionnaire, "_wait_for_chatgpt_answers", lambda: [])

    result = questionnaire.start_chatgpt_questionnaire_fallback(
        executor=lambda *_: {"status": "stopped"},
        reason="quota exceeded",
    )

    assert result["status"] == "fallback_opened"
    assert opened == [questionnaire.CHATGPT_TEMPORARY_CHAT_URL]
    assert typed and "contraseñas seguras" in typed[0]


def test_chatgpt_autofill_uses_local_locator_after_gemini_quota() -> None:
    calls: list[tuple[str, dict]] = []

    def executor(name, arguments):
        calls.append((name, arguments))
        return {
            "status": "clicked" if name == "questionnaire_local_click" else "completed"
        }

    results = questionnaire._fill_fallback_answers(
        executor,
        [{"question": "2 + 2?", "control": "text", "answer": "4"}],
    )

    assert results[0]["status"] == "completed"
    assert calls[0][0] == "questionnaire_local_click"
    assert not any(name == "vision_click" for name, _ in calls)


def test_missing_inspection_coordinates_stop_before_typing(monkeypatch) -> None:
    monkeypatch.setattr(
        questionnaire,
        "inspect_visible_questionnaire",
        lambda: {
            "capture": {"origin_x": 0, "origin_y": 0, "width": 1000, "height": 800},
            "questions": [
                {
                    "question": "2 + 2?",
                    "answer": "4",
                    "control": "text",
                    "target": "answer field",
                    "confidence": 0.99,
                }
            ],
        },
    )
    calls: list[tuple[str, dict]] = []

    result = questionnaire.complete_visible_questionnaire(
        lambda name, arguments: calls.append((name, arguments))
        or {"status": "completed"}
    )

    assert result["filled"] == 0
    assert result["status"] == "stopped"
    assert calls == []


def test_field_interaction_error_stops_without_delegating_typing(monkeypatch) -> None:
    monkeypatch.setattr(
        questionnaire,
        "inspect_visible_questionnaire",
        lambda: {
            "capture": {"origin_x": 0, "origin_y": 0, "width": 1000, "height": 800},
            "questions": [
                {
                    "question": "2 + 2?",
                    "answer": "4",
                    "control": "text",
                    "target": "answer field",
                    "target_point_2d": [500, 500],
                    "confidence": 0.99,
                }
            ],
        },
    )

    def executor(name, arguments):
        raise RuntimeError("field focus failed")

    result = questionnaire.complete_visible_questionnaire(executor)

    assert result["status"] == "stopped"
    assert result["filled"] == 0
    assert "must not ask" in result["message"]
