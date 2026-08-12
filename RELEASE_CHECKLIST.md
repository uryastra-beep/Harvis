# Harvis v1.0.0 Release Checklist

Use this checklist before creating the first public Harvis release. GitHub release publication is intentionally manual.

## 1. Sync and environment

- [ ] Pull the latest `main` branch.
- [ ] Confirm the working tree has no unintended local changes.
- [ ] Confirm Python 3.11 or newer is being used.
- [ ] Activate `.venv` or use its Python executable directly.
- [ ] Refresh dependencies with `python -m pip install -r requirements.txt`.
- [ ] Confirm `harvis.__version__` reports `1.0.0`.

Version check:

```powershell
python -c "import harvis; print(harvis.__version__)"
```

Expected output:

```text
1.0.0
```

## 2. Automated checks

- [ ] Run the full test suite.

```powershell
python -m pytest
```

- [ ] Confirm there are no failed tests.
- [ ] Confirm there are no syntax or import failures.
- [ ] If anything is skipped because of the local environment, record it before publishing instead of describing the suite as fully passed.

## 3. Core Windows runtime

- [ ] Start Harvis with `python -m harvis`.
- [ ] Confirm a second normal launch activates the existing Harvis instance instead of creating a duplicate.
- [ ] Confirm the startup greeting works in Speaking mode.
- [ ] Confirm Gemini Live remains responsive after idle time.
- [ ] Confirm connection rotation or a transient disconnect triggers bounded recovery instead of requiring a Harvis restart.
- [ ] Confirm reconnecting does not replay the startup greeting.
- [ ] Confirm Harvis self-shutdown closes Harvis only.
- [ ] Confirm `START_HARVIS.vbs` launches without leaving a terminal visible.
- [ ] Confirm `%APPDATA%\Harvis\harvis.log` receives runtime output from the VBS launcher.

## 4. Speaking and Silent modes

- [ ] Confirm microphone input works in Speaking mode.
- [ ] Confirm Gemini native voice output works.
- [ ] Confirm configured voice volume and preferred language are respected.
- [ ] Confirm Sphere and Bars react to real Gemini audio.
- [ ] Confirm the Sphere loading animation appears while Harvis processes a request and returns when appropriate.
- [ ] Short-click Sphere to mute and unmute microphone forwarding without reconnecting Gemini Live.
- [ ] Confirm the muted Sphere indicator is visible.
- [ ] Confirm dragging Sphere does not toggle microphone state.
- [ ] Switch to Silent mode and confirm microphone and speaker streams are not used.
- [ ] Confirm the compact Silent popup accepts typed commands without a wake name.
- [ ] Switch back to Speaking mode and confirm the normal live surface returns.

Visualizer previews:

```powershell
python -m harvis --visualizer-preview sphere
python -m harvis --visualizer-preview bars
```

## 5. Desktop actions and guarded workflows

Use harmless test targets.

- [ ] Open and close an installed application.
- [ ] Open an HTTP or HTTPS URL.
- [ ] Change master volume.
- [ ] Perform a browser action and a media action.
- [ ] Scroll a page or document.
- [ ] Type Unicode text and a multi-line sequence using physical Enter handling.
- [ ] Run a harmless workflow containing at least three ordered actions.
- [ ] Confirm long workflows wait for screen stability after UI-changing actions.
- [ ] Confirm a required `ready_target` prevents a dependent action from running until the target appears.
- [ ] Confirm `vision_click` waits for its target before clicking.
- [ ] Confirm missing or low-confidence targets stop the remaining workflow.
- [ ] Confirm invalid plans fail before the first action runs.
- [ ] Confirm one-step and two-step plans remain responsive without unnecessary long-workflow guards.
- [ ] Confirm sensitive visual actions require real user confirmation.
- [ ] Confirm an AI-supplied confirmation argument cannot bypass the local confirmation gate.

## 6. Mobile remote and voice routing

Use a phone on the same trusted private LAN.

- [ ] Confirm mobile remote control is off by default.
- [ ] Enable it from `Settings > Advanced` and save.
- [ ] Confirm Harvis shows a phone URL and six-digit pairing code.
- [ ] Open the phone URL and confirm the controller loads.
- [ ] Confirm a wrong pairing code is rejected.
- [ ] Pair successfully and confirm status polling begins.
- [ ] Send a harmless remote command in Speaking mode.
- [ ] Send a harmless remote command in Silent mode.
- [ ] Confirm the latest response transcript appears on the phone.
- [ ] Toggle microphone mute from the phone and confirm the desktop Sphere stays in sync.
- [ ] Select `Computer only` and confirm Harvis voice plays only on the PC.
- [ ] Select `Phone only`, enable browser audio if requested, and confirm the PC stays quiet while Harvis voice plays on the phone.
- [ ] Select `Phone + computer` and confirm the same Harvis response plays on both devices.
- [ ] Confirm switching back to `Computer only` stops phone playback.
- [ ] Restart Harvis and confirm the old browser token requires pairing again.
- [ ] Confirm the new pairing code works after restart.
- [ ] Disable mobile remote control and confirm the local server stops.
- [ ] Confirm stopping the remote restores voice routing to `Computer only`.
- [ ] Do not configure router port forwarding for the Harvis remote port.

## 7. Local knowledge, files, routines, plugins, and Undo

- [ ] Add, update, recall, and delete a harmless non-secret memory.
- [ ] Confirm password, API-key, token, and secret-like memories are rejected.
- [ ] Add and open a temporary friendly link from `links.txt`, then remove it.
- [ ] Open representative exact-name folder, image, PDF, video, and text-file items.
- [ ] Confirm duplicate exact-name matches return ambiguity rather than guessing.
- [ ] Copy, move, and rename temporary test items without overwriting existing destinations.
- [ ] Confirm supported move or rename actions can be reverted with safe Undo.
- [ ] Confirm Trash and folder organization require real subsequent confirmation.
- [ ] Save, run, and delete a harmless routine.
- [ ] Run bundled JSON-only plugins and confirm arbitrary Python plugin files are not executed.
- [ ] Inspect the activity log and confirm typed content, memory values, keys, tokens, and passwords are not stored in plaintext.
- [ ] Explicitly request clipboard context and confirm Harvis uses current clipboard content without maintaining a history.

## 8. Image and questionnaire assistance

- [ ] Analyze a harmless exact-name local image and confirm the description matches the image.
- [ ] Confirm instructions shown inside an image are treated as untrusted content.
- [ ] Open a harmless visible questionnaire.
- [ ] Ask Harvis to complete it correctly and confirm confident visible fields are filled.
- [ ] Confirm text and multiple-choice answers are placed in the intended fields.
- [ ] Confirm Harvis stops instead of guessing when an answer or field cannot be identified confidently.
- [ ] Confirm Harvis never clicks `Submit`, `Finish`, `Send`, `Next`, or another committing control automatically.
- [ ] Review the completed questionnaire manually before submission.
- [ ] If practical, test the bounded temporary ChatGPT fallback by making Gemini questionnaire analysis unavailable on Windows.

## 9. Wake word and system tray

- [ ] Enable local Windows wake word.
- [ ] Say Harvis or Jarvis and confirm Gemini connects after local recognition.
- [ ] Let the configured active-session timeout expire and confirm Harvis returns to local wake listening.
- [ ] Close Settings and confirm Harvis remains available from the tray when enabled.
- [ ] Test tray mode switching, microphone control, Undo, and full exit.

## 10. Credentials and persistence

- [ ] Confirm Settings reports the Gemini API key as configured without revealing it.
- [ ] Confirm an empty API-key field preserves the saved key.
- [ ] Confirm replacing the API key restarts the assistant cleanly.
- [ ] Confirm the key is absent from `settings.json`.
- [ ] Confirm child applications launched by Harvis do not inherit a saved Gemini key through their environment.
- [ ] Confirm settings survive a Harvis restart.
- [ ] Confirm remote enabled state and LAN port persist.
- [ ] Confirm remote pairing codes and browser tokens are not persisted in `settings.json`.

## 11. Windows portable build

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_exe.ps1
```

- [ ] Confirm the test suite passes during the build script.
- [ ] Confirm `dist\Harvis\Harvis.exe` is created.
- [ ] Launch the packaged executable and repeat a short Speaking, Silent, visual, and remote smoke test.
- [ ] Confirm packaged Harvis can find its required dependencies.
- [ ] Confirm no development API key or personal file is bundled into `dist\Harvis`.

## 12. Windows installer

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_installer.ps1 -Version "1.0.0"
```

Expected artifact:

```text
dist\installer\Harvis-Setup-1.0.0-Windows-x64.exe
```

- [ ] Confirm the installer is created with the expected name.
- [ ] Install Harvis per-user.
- [ ] Confirm the installed app launches.
- [ ] Confirm optional desktop and startup shortcuts behave correctly.
- [ ] Confirm uninstall completes cleanly.
- [ ] Remember that the current installer is unsigned and can trigger SmartScreen or unknown-publisher warnings.

## 13. GitHub Windows package workflow

- [ ] Run `Windows package` manually with version `1.0.0` or trigger it from the final `v1.0.0` tag.
- [ ] Confirm the workflow build succeeds.
- [ ] Download the `Harvis-Setup-1.0.0-Windows-x64` artifact.
- [ ] Smoke-test the downloaded artifact, not only the locally built installer.

## 14. Repository final review

- [ ] Confirm `README.md` describes the current `main` branch accurately.
- [ ] Confirm `RELEASE_NOTES.md` is titled `Harvis v1.0.0 Release Notes`.
- [ ] Confirm `LICENSE` contains the complete GNU GPLv3 license.
- [ ] Confirm no API keys, secrets, logs, `.venv`, build output, or personal temporary files are tracked.
- [ ] Confirm committed repository text is in English.
- [ ] Confirm the final release commit has the expected GitHub checks or workflows completed.

## 15. Manual GitHub release

Only after the applicable checks above are complete:

- [ ] Create tag `v1.0.0` from the final release commit.
- [ ] Create GitHub release `Harvis v1.0.0`.
- [ ] Use `RELEASE_NOTES.md` as the release description basis.
- [ ] Attach `Harvis-Setup-1.0.0-Windows-x64.exe` and any intended portable archive.
- [ ] Disclose that Windows artifacts are currently unsigned.
- [ ] Publish the release manually.

## Release status

Do not publish v1.0.0 until the automated suite, packaged-runtime smoke test, installer smoke test, and critical safety checks above have passed. Harvis should fail safely when visual confidence, questionnaire confidence, or confirmation requirements are not satisfied.
