# Harvis Release Notes Draft

> Replace the version placeholder below before publishing the GitHub release.

## Harvis vX.Y.Z

Harvis is a Python desktop personal assistant that combines Gemini Live conversation with approved local computer-control tools, visual interaction, configurable Speaking and Silent modes, optional audio-reactive visualizers, and paired mobile control over the local network.

### Highlights

- Gemini Live native-audio conversation with Spanish (Latin America) and English response preferences.
- Automatic Gemini Live reconnection after idle or server-side connection rotation, with session resumption when a resumable handle is available.
- Context-window compression for longer-running Live sessions.
- Multi-step task orchestration for long single-instruction desktop workflows.
- Automatic screen-stability and visible-target readiness guards for workflows with more than two steps.
- Paired mobile remote control from a phone browser on the same trusted local network.
- Speaking mode for microphone and voice interaction.
- Silent mode with a compact transparent text-command popup and no microphone or speaker streams.
- Secure Gemini API key storage from Settings.
- Single-instance startup behavior that reactivates the existing Harvis process.
- Local application discovery for opening and closing installed apps.
- Browser, media, system-volume, keyboard, mouse, scrolling, and Harvis self-shutdown tools.
- Visual clicking with Gemini Vision as the primary locator, a local fallback stack, and a final Gemini Vision retry.
- Locally enforced confirmation for sensitive or destructive visual actions that cannot be bypassed by an AI-supplied flag.
- Live Sphere and Bars visualizers driven by Gemini output audio.
- Click the live Sphere to mute or unmute microphone forwarding without disconnecting Gemini Live.
- A visible diagonal indicator on the Sphere while the microphone is muted.
- Smooth Sphere-to-spinner transition while Harvis is processing a request or searching for a visual target.
- Optional `#G6m2i9` AI-authorship watermark for content Harvis is asked to write.
- Watermark intent filtering so searches, URLs, navigation, and other operational typing stay unmarked.
- Improved Unicode typing and explicit physical Enter handling.
- Cleaner Gemini Live startup, shutdown, latency, and reconnect behavior.
- User-controlled local memory with explicit secret rejection.
- Exact-name opening for folders, photos, videos, PDFs, documents, and other files.
- Guarded copy, move, rename, Trash, and folder-organization operations.
- Editable friendly web shortcuts through `links.txt`.
- Local-image descriptions and visible-questionnaire assistance.
- A temporary ChatGPT questionnaire fallback when Gemini analysis is unavailable on Windows.
- Reusable routines, JSON-only plugins, redacted activity history, and limited safe Undo.
- Optional local Windows wake-word activation and a configurable active-session timeout.
- System-tray controls for mode, microphone, Undo, and exit.
- GitHub release checks, a PyInstaller executable build, an Inno Setup installer, and a Windows packaging workflow.

### Local knowledge and automation

Harvis now stores explicit non-secret memories in a bounded local file managed from `Settings > Knowledge`. It rejects password, API-key, token, and secret-like entries. The same page provides direct access to friendly named links, saved routines, JSON-only plugins, and the redacted activity log.

Routines and plugins execute only through the existing guarded action planner. Plugin files are declarative JSON; Harvis does not import or execute plugin Python code. Activity history omits typed content and secret-like arguments, while Undo is exposed only for a small set of actions that recorded a safe inverse.

### Files, images, and questionnaires

Harvis can find standard user-folder items by exact name and open them with the operating system default application. Explicit requests can copy, move, or rename without overwriting. Trash and folder organization require a real subsequent confirmation, and deletion remains recoverable through the operating system Trash.

Gemini Vision can briefly describe an exact-name local image. For visible questionnaires, Harvis uses one guarded inspection, fills exact visible answer points from bottom to top, and never submits the form. When Gemini analysis is unavailable on Windows, a bounded temporary-ChatGPT fallback can copy visible question text, obtain structured answers, return to the form, and use only offline field location. Educational password questions no longer trigger the credential-field block. If safe automatic filling cannot continue, Harvis stops instead of delegating typing to the user. The user remains responsible for review and submission.

### Wake word, tray, and packaging

Optional local wake-word mode uses Windows SAPI to recognize Harvis or Jarvis before opening the Gemini Live microphone session. System-tray controls keep common actions available when the Settings window is hidden.

The repository now contains repeatable Windows executable and installer scripts. A packaging workflow uploads a tested installer artifact but intentionally leaves GitHub release publication manual.

### Mobile remote control

Settings > Advanced now includes a `Mobile remote control` group. When enabled, Harvis serves a responsive controller to devices on the same local network and shows both the phone URL and a six-digit pairing code inside the Settings window.

The paired phone page can send text commands to the active Gemini Live assistant in either Speaking or Silent mode, read the latest Harvis status and response transcript, and mute or unmute microphone forwarding while Harvis is in Speaking mode.

Pairing returns a random browser token. The pairing code and browser token are regenerated whenever the remote server restarts, including when Harvis restarts or the configured LAN port changes. Repeated incorrect pairing attempts are rate-limited.

The server accepts only private, loopback, or link-local client addresses. It is intended for trusted local networks and does not require Internet port forwarding. The current controller uses local HTTP rather than TLS, so it must not be exposed to public or untrusted networks.

### Multi-step task orchestration

Harvis includes an `execute_action_plan` tool backed by a local task-orchestration layer. Gemini can convert one long user instruction into an ordered plan of approved actions instead of relying on a loose sequence of independent function calls.

Plans are validated completely before execution and are bounded to 24 steps. They can include application open or close actions, URLs, volume changes, browser and media controls, pointer movement, scrolling, visual clicks, typing, physical Enter presses, and short waits for UI transitions.

When a plan contains more than two steps, Harvis treats it as a guarded long workflow. After UI-changing actions, Harvis samples the visible desktop and waits for the screen to settle before allowing the next step to run. Short one-step and two-step plans do not receive these extra readiness checks.

A step can also declare a `ready_target` when it must wait for a specific visible button, field, icon, text label, or UI state. Harvis keeps checking for the target for a bounded period and stops the remaining plan if it never becomes confidently visible. `vision_click` steps automatically use their own click target as a readiness checkpoint, so Harvis will not attempt the click until the requested target has appeared.

Screen-stability checks default to a bounded six-second window. Visible readiness targets default to ten seconds and can be configured up to fifteen seconds. These checks are intentionally fail-safe: an unavailable screen capture, a screen that never settles, a missing target, or a low-confidence target stops the workflow instead of letting later steps run against the wrong UI.

Explicit wait steps are still capped at 5 seconds each and 15 seconds total per plan. Harvis self-shutdown cannot be placed inside a plan.

The orchestrator also stops when an action fails, Gemini Vision is unavailable for a required visual step, or a sensitive visual action requires confirmation. Dynamic workflows whose later steps depend on an unknown newly observed UI state can use the plan for the deterministic prefix and then continue with individual tools.

### Gemini Live session recovery

Harvis enables Gemini Live session resumption and context-window compression. If a long-running Live connection is rotated or drops after Harvis has been idle, Harvis keeps the desktop process alive and attempts to reconnect with bounded exponential backoff instead of leaving the assistant permanently unresponsive.

When Gemini provides a resumable session handle, Harvis reuses the latest valid handle on the next connection so conversational state can continue across the WebSocket rotation. Reconnects do not replay the normal startup greeting. Typed Silent-mode commands that fail during transport are returned to the local queue for a retry after reconnection.

After repeated rapid reconnect failures, Harvis stops retrying and surfaces an unavailable status instead of creating an endless reconnect loop.

### Sphere microphone control

In Speaking mode, a short click on the live Sphere toggles microphone forwarding. Harvis keeps the Gemini Live session connected and leaves the audio stream open, so unmuting is immediate.

Dragging the Sphere continues to reposition it without toggling the microphone. While muted, the Sphere displays a diagonal tertiary-color indicator. The same microphone state can now be toggled from an authenticated mobile remote.

### Sphere loading state

When Harvis starts processing a recognized request, the live Sphere smoothly shrinks and fades into a rotating multi-ring loading indicator using the Harvis secondary and tertiary colors. It returns to the normal audio-reactive Sphere when a response begins.

Visual target searches explicitly reactivate the loading state while the locator is working and return to the normal Sphere when the visual action succeeds, fails safely, or requires confirmation.

### AI watermark behavior

When `AI watermark` is enabled in Settings > AI, Harvis prefixes AI-authored content with:

```text
#G6m2i9 
```

The watermark is intended for written content that Harvis authors. It is not added to search queries, URLs, browser navigation, or similar operational text entry. Mobile commands use the same local watermark-intent path as other text instructions.

### Visual fallback behavior

Harvis currently uses this visual target strategy:

```text
Gemini Vision
    -> local locator fallback when Gemini is unavailable or uncertain
    -> final Gemini Vision retry if local detection also misses
    -> fail safely when no confident target is found
```

The local locator uses accessibility information and local visual evidence rather than random low-confidence clicking.

Sensitive visual clicks now require a real subsequent user confirmation recorded by the local runtime. Confirmation
authorizes only one retry for the same target and click type; an AI-generated argument cannot self-approve the action.

### Setup

Windows quick start:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m harvis
```

After setup, `START_HARVIS.vbs` can launch Harvis without leaving a terminal window visible.

To use the mobile controller, enable it in Settings > Advanced, save settings, then open the displayed phone URL from a device on the same trusted local network and enter the displayed pairing code.

### Important notes

- A Gemini API key is required for Gemini Live and Gemini Vision.
- Cloud features are subject to the limits of the configured Google API project.
- Multi-step plans intentionally stop on screen-readiness failures, missing targets, uncertainty, or confirmation-required visual actions rather than guessing through unknown UI states.
- Screen-stability detection is a visual heuristic; highly animated desktops may take longer to be considered settled or may stop a guarded plan safely.
- Mobile remote control is LAN-only and currently uses HTTP rather than TLS. Do not expose its port to the public Internet or use it on an untrusted network.
- Windows is currently the most heavily tested platform.
- Linux support is present for several system integrations, but some desktop-control features still depend on X11-compatible tools and are not fully Wayland-ready.
- The executable and installer are not code-signed, so Windows may show an unknown-publisher warning.
- Harvis is licensed under GNU GPLv3; see `LICENSE`.

### Before publishing

Complete the checks in `RELEASE_CHECKLIST.md`, choose the final version/tag, and edit this file if the release should mention additional known limitations or platform requirements.
