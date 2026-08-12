from __future__ import annotations

from typing import Any

from harvis.core.task_orchestrator import task_plan_tool_declaration


def feature_tool_declarations() -> list[dict[str, Any]]:
    """Return Gemini declarations for modular Harvis capabilities."""

    plan_steps_schema = task_plan_tool_declaration()["parameters"]["properties"][
        "steps"
    ]

    return [
        {
            "name": "remember_preference",
            "description": (
                "Store a non-secret fact or preference locally only when the user explicitly asks Harvis to "
                "remember it. Never store passwords, API keys, tokens, financial data, or secrets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "maxLength": 120},
                    "value": {"type": "string", "maxLength": 2000},
                },
                "required": ["key", "value"],
            },
        },
        {
            "name": "recall_memory",
            "description": "Search user-controlled local Harvis memories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 200},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
            },
        },
        {
            "name": "forget_memory",
            "description": "Delete one local Harvis memory by its exact key when the user explicitly asks.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "maxLength": 120}},
                "required": ["key"],
            },
        },
        {
            "name": "open_exact_file_or_folder",
            "description": (
                "Find and open a folder, photo, video, PDF, document, or other local item using its exact file "
                "name. If several exact matches exist, return them and ask the user which one; never guess."
            ),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 260}},
            "required": ["name"],
            },
        },
        {
            "name": "copy_exact_file_or_folder",
            "description": (
                "Copy one local item identified by its exact name into an existing destination folder identified "
                "by its exact name. Never overwrite an existing destination."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "maxLength": 260},
                    "destination_folder_name": {"type": "string", "maxLength": 260},
                },
                "required": ["source_name", "destination_folder_name"],
            },
        },
        {
            "name": "move_exact_file_or_folder",
            "description": (
                "Move one local item identified by its exact name into an existing destination folder. Never "
                "overwrite. Use only after an explicit user request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "maxLength": 260},
                    "destination_folder_name": {"type": "string", "maxLength": 260},
                },
                "required": ["source_name", "destination_folder_name"],
            },
        },
        {
            "name": "rename_exact_file_or_folder",
            "description": "Rename one exact local file or folder without overwriting another item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "maxLength": 260},
                    "new_name": {"type": "string", "maxLength": 260},
                },
                "required": ["source_name", "new_name"],
            },
        },
        {
            "name": "delete_exact_file_or_folder",
            "description": (
                "Move one exact local file or folder to the operating system trash. This always requires a real "
                "subsequent user confirmation and is never permanently deleted by Harvis."
            ),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 260}},
                "required": ["name"],
            },
        },
        {
            "name": "organize_folder_by_type",
            "description": (
                "Organize the top-level files in one exact folder into Images, Videos, Audio, Documents, Archives, "
                "and Other subfolders. Requires a real subsequent user confirmation before moving anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {"folder_name": {"type": "string", "maxLength": 260}},
                "required": ["folder_name"],
            },
        },
        {
            "name": "open_named_link",
            "description": (
                "Open a URL by the exact friendly name configured in Harvis links.txt, such as Oxford or Woot it."
            ),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 80}},
                "required": ["name"],
            },
        },
        {
            "name": "read_clipboard",
            "description": (
                "Read the user's current text clipboard only when the user explicitly asks about what they copied."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "analyze_image_file",
            "description": (
                "Analyze a user-selected local image by exact file name and return a short description or answer "
                "a specific question about it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 260},
                    "question": {"type": "string", "maxLength": 1000},
                },
                "required": ["name"],
            },
        },
        {
            "name": "complete_visible_questionnaire",
            "description": (
                "Inspect the currently visible questionnaire, infer answers, and fill confident visible fields. "
                "Use only when the user explicitly asks Harvis to complete the questionnaire. Harvis never clicks "
                "Submit, Finish, Send, or another committing control; the user must review and submit. If Gemini "
                "Vision is unavailable, Harvis opens a temporary ChatGPT chat and copies the visible questions for "
                "answer assistance."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "save_routine",
            "description": (
                "Save a user-named routine as a reusable guarded action plan. Only save it when the user explicitly "
                "asks to create or remember a routine."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 80},
                    "steps": plan_steps_schema,
                },
                "required": ["name", "steps"],
            },
        },
        {
            "name": "run_routine",
            "description": "Run an existing user-named routine through Harvis's guarded task orchestrator.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 80}},
                "required": ["name"],
            },
        },
        {
            "name": "list_routines",
            "description": "List locally saved Harvis routines.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "delete_routine",
            "description": "Delete one saved routine when the user explicitly requests it.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 80}},
                "required": ["name"],
            },
        },
        {
            "name": "recent_activity",
            "description": "Show a bounded local history of Harvis actions without exposing typed content.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            },
        },
        {
            "name": "undo_last_action",
            "description": (
                "Undo the latest Harvis action only when that action recorded a safe supported inverse. Never claim "
                "that an unsupported action can be undone."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "list_plugins",
            "description": "List safe data-only Harvis plugins installed in the local plugins directory.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "run_plugin",
            "description": "Run a named data-only Harvis plugin as a guarded action plan.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 80}},
                "required": ["name"],
            },
        },
    ]


__all__ = ["feature_tool_declarations"]
