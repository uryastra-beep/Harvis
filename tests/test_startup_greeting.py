from harvis.assistant import HarvisGeminiLiveVoice


def _noop_tool(name, arguments):
    return {"name": name, "arguments": arguments}


def test_startup_greeting_prompt_uses_configured_name() -> None:
    voice = HarvisGeminiLiveVoice(
        user_name="Santi",
        execute_tool=_noop_tool,
    )

    prompt = voice._startup_greeting_prompt()

    assert "Santi" in prompt
    assert "configured preferred language" in prompt
    assert "Do not call tools" in prompt


def test_user_name_is_normalized_before_greeting() -> None:
    voice = HarvisGeminiLiveVoice(
        user_name="  Santi    Astra  ",
        execute_tool=_noop_tool,
    )

    prompt = voice._startup_greeting_prompt()

    assert "Santi Astra" in prompt
    assert "Santi    Astra" not in prompt
