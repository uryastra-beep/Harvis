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
            "name": "semantic_search_files",
            "description": (
                "Search local files by meaning, partial names, document content, file type, and recency. Use this "
                "for requests such as finding a PDF about Greece used last week when the exact filename is unknown."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 500},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 12},
                },
                "required": ["query"],
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
                "answer assistance. If automatic completion stops, report the reason without asking the user to "
                "type the answers manually and without switching to general typing tools."
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
            "name": "schedule_reminder",
            "description": (
                "Schedule a local Harvis reminder. Convert the user's requested local date and time to an explicit "
                "ISO-8601 timestamp with timezone before calling."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "maxLength": 500},
                    "run_at": {"type": "string", "maxLength": 64},
                    "recurrence": {
                        "type": "string",
                        "enum": ["once", "daily", "weekly"],
                    },
                },
                "required": ["message", "run_at"],
            },
        },
        {
            "name": "schedule_routine",
            "description": (
                "Schedule an existing guarded Harvis routine for a specific ISO-8601 time, optionally daily or weekly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 80},
                    "run_at": {"type": "string", "maxLength": 64},
                    "recurrence": {
                        "type": "string",
                        "enum": ["once", "daily", "weekly"],
                    },
                },
                "required": ["name", "run_at"],
            },
        },
        {
            "name": "list_scheduled_items",
            "description": "List local reminders and scheduled routines.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "cancel_scheduled_item",
            "description": "Cancel one reminder or routine schedule by its displayed ID.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string", "maxLength": 32}},
                "required": ["id"],
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
            "name": "explain_last_failure",
            "description": "Explain why the most recent recorded Harvis action failed or stopped.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "run_self_check",
            "description": "Run Harvis local health and configuration diagnostics.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "export_diagnostics",
            "description": (
                "Create a privacy-bounded diagnostic ZIP with redacted settings and log tails when the user asks "
                "to export diagnostics or prepare a bug report."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "visual_memory_stats",
            "description": "Show how many verified on-screen target locations Harvis has learned locally.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "clear_visual_memory",
            "description": "Clear learned UI locations only when the user explicitly asks.",
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
        {
            "name": "install_plugin_file",
            "description": (
                "Install a safe data-only Harvis plugin from an exact local JSON filename after the user explicitly "
                "asks to install it. The action plan is validated before installation."
            ),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 260}},
                "required": ["name"],
            },
        },
        {
            "name": "remove_plugin",
            "description": "Remove one installed data-only plugin when the user explicitly asks.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "maxLength": 80}},
                "required": ["name"],
            },
        },
        {
            "name": "send_phone_notification",
            "description": (
                "Send a short useful status or result to the paired phone remote when the user asks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "maxLength": 80},
                    "message": {"type": "string", "maxLength": 500},
                },
                "required": ["title", "message"],
            },
        },
    ]


__all__ = ["feature_tool_declarations"]
