from harvis.assistant import HarvisGeminiLiveVoice


def test_gemini_registers_next_generation_feature_tools() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    names = {
        declaration["name"]
        for declaration in declarations[0]["function_declarations"]
    }

    assert {
        "remember_preference",
        "recall_memory",
        "forget_memory",
        "open_exact_file_or_folder",
        "copy_exact_file_or_folder",
        "move_exact_file_or_folder",
        "rename_exact_file_or_folder",
        "delete_exact_file_or_folder",
        "organize_folder_by_type",
        "open_named_link",
        "read_clipboard",
        "analyze_image_file",
        "complete_visible_questionnaire",
        "save_routine",
        "run_routine",
        "recent_activity",
        "undo_last_action",
        "list_plugins",
        "run_plugin",
    }.issubset(names)


def test_saved_routine_schema_reuses_the_guarded_plan_actions() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()[0][
        "function_declarations"
    ]
    by_name = {declaration["name"]: declaration for declaration in declarations}

    routine_steps = by_name["save_routine"]["parameters"]["properties"]["steps"]
    plan_steps = by_name["execute_action_plan"]["parameters"]["properties"]["steps"]

    assert routine_steps == plan_steps
    assert "action" in routine_steps["items"]["required"]
    assert "shutdown_harvis" not in routine_steps["items"]["properties"]["action"]["enum"]
