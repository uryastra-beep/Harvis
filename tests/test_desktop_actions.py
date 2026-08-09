import pytest

from harvis.actions.desktop import normalize_application_name
from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisGeminiLiveVoice


def test_application_aliases_are_normalized() -> None:
    assert normalize_application_name("Google Chrome") == "chrome"
    assert normalize_application_name("Visual Studio Code") == "vscode"
    assert normalize_application_name("File Explorer") == "explorer"


def test_unknown_application_is_rejected() -> None:
    with pytest.raises(SystemActionError):
        normalize_application_name("definitely-not-an-installed-app")


def test_gemini_registers_desktop_control_tools() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    function_names = {
        function["name"]
        for function in declarations[0]["function_declarations"]
    }

    assert {
        "set_master_volume",
        "open_url",
        "open_application",
        "close_application",
        "browser_control",
        "media_control",
    }.issubset(function_names)
