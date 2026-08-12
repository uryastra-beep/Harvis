from harvis.features import questionnaire


def test_questionnaire_fills_visible_answers_but_never_submits(monkeypatch) -> None:
    monkeypatch.setattr(
        questionnaire,
        "inspect_visible_questionnaire",
        lambda: {
            "questions": [
                {
                    "question": "2 + 2?",
                    "answer": "4",
                    "control": "choice",
                    "target": "answer option 4",
                    "confidence": 0.99,
                },
                {
                    "question": "Name a color",
                    "answer": "Blue",
                    "control": "text",
                    "target": "text field under Name a color",
                    "confidence": 0.9,
                },
                {
                    "question": "Finish",
                    "answer": "Submit",
                    "control": "choice",
                    "target": "Submit answers button",
                    "confidence": 1.0,
                },
            ]
        },
    )
    calls: list[tuple[str, dict]] = []

    def executor(name, arguments):
        calls.append((name, arguments))
        return {"status": "clicked" if name == "vision_click" else "completed"}

    result = questionnaire.complete_visible_questionnaire(executor)

    assert result["filled"] == 2
    assert result["submitted"] is False
    assert (
        "type_text_unwatermarked",
        {"text": "Blue"},
    ) in calls
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
