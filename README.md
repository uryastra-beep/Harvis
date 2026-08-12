# Harvis

Harvis is a cross-platform desktop personal assistant built in Python. It combines real-time Gemini Live conversation, local computer and file control, visual interaction, guarded multi-step task execution, configurable Speaking and Silent modes, optional audio-reactive visualizers, and paired mobile control over a trusted local network.

The project currently targets Windows most strongly while keeping the architecture portable to Linux wherever the underlying system integrations allow it.

> **Development status:** this README documents the current `main` branch, including features that may not yet exist in a published release.

## Highlights

- Real-time voice conversation through Gemini Live.
- Automatic Live-session recovery with session resumption, context-window compression, and bounded reconnect backoff.
- Speaking and Silent interaction modes.
- Desktop control through approved local tools.
- Multi-step task orchestration for long single-instruction workflows.
- Automatic screen-stability and visible-target readiness guards for workflows with more than two steps.
- Paired mobile remote control over the local network.
- Selectable Harvis voice routing: computer only, phone only, or phone and computer together.
- Authenticated phone-side playback of the same native Gemini Live audio used by the desktop assistant.
- Application discovery and launch support.
- Browser, media, volume, keyboard, mouse, scrolling, and Harvis self-shutdown actions.
- Visual clicking with Gemini Vision plus a local fallback stack.
- Sensitive visual actions require confirmation before clicking.
- Secure Gemini API key storage from the Settings UI.
- Single-instance behavior to avoid duplicate Harvis processes.
- Sphere and Bars audio-reactive visualizers.
- Click-to-mute microphone control on the live Sphere without disconnecting Gemini Live.
- Smooth Sphere-to-spinner loading animation while Harvis processes requests and visual searches.
- Optional AI-authorship watermark for content Harvis writes.
- Persistent settings with a PySide6 liquid-glass interface.
- User-controlled local memory that refuses passwords, tokens, API keys, and secrets.
- Exact-name file and folder opening, plus guarded copy, move, rename, Trash, and folder-organization actions.
- Friendly named links stored in an editable `links.txt` file.
- Short Gemini Vision descriptions of exact-name local image files.
- Visible-questionnaire assistance with confident field filling and no automatic submission.
- Temporary ChatGPT browser fallback when Gemini questionnaire analysis is unavailable on Windows.
- Reusable guarded routines and JSON-only declarative plugins.
- Bounded, redacted activity history and limited safe Undo.
- Local clipboard context only after an explicit user request.
- Local Windows wake-word mode that can avoid a continuous Gemini microphone connection.
- Persistent system-tray controls, including mode switching, microphone control, NovaLens, and Undo.
- Local same-user NovaLens companion bridge for questions, screen-region analysis, and recent audio.
- Startup update checks, a portable Windows executable build, and an Inno Setup installer workflow.

## Official color palette

- Primary: `#00072B`
- Secondary: `#85B1FF`
- Tertiary: `#53EEFC`

## Interaction modes

### Speaking

Speaking mode uses the microphone and Gemini Live native audio output. Harvis listens for requests addressed to `Harvis` or `Jarvis`, answers with voice, and can execute approved desktop tools.

On Windows, `Settings > Advanced > Local wake word` can keep Gemini disconnected until Windows SAPI recognizes `Harvis` or `Jarvis` locally. After activation, Gemini Live handles the request and stays available for the configured 30-to-600-second idle window before Harvis returns to local listening. This optional mode is off by default because Windows speech-recognizer availability and accuracy vary by installed language pack and microphone.

When the visualizer is enabled:

- `Sphere` opens a small transparent always-on-top orb.
- `Bars` opens the frequency-bar visualizer.

A short click on the live Sphere toggles microphone forwarding on or off without closing the audio stream or disconnecting the Gemini Live session. When muted, the Sphere displays a diagonal tertiary-color indicator. Dragging the Sphere still moves it and does not toggle the microphone.

When Harvis starts processing a recognized request, the live Sphere smoothly shrinks and fades into a rotating multi-ring loading indicator using the Harvis secondary and tertiary colors. It returns to the normal audio-reactive sphere when a response begins or the current visual search finishes. Visual target searches explicitly keep the loading state active while Harvis is locating the requested UI element.

### Silent

Silent mode is designed for places where voice interaction is inconvenient. Harvis does not open microphone or speaker streams in this mode. Instead, it shows a compact always-on-top text popup.

Typed Silent-mode commands are treated as directly addressed to Harvis, so the wake name is not required.

Examples:

```text
Open Chrome
Set volume to 25 percent
Click the GitHub tab
Scroll down
```

The Silent popup intentionally hides detailed visual target names while Harvis is searching so the popup itself does not interfere with visual target detection.

## Mobile remote control

Harvis can expose a responsive controller to phones and tablets on the same trusted local network. The feature is disabled by default.

### Enable the remote

1. Open `Settings > Advanced`.
2. Set `Remote control` to `On`.
3. Keep the default LAN port or choose another port between 1024 and 65535.
4. Save settings.
5. Open the displayed `Phone URL` on a phone connected to the same local network.
6. Enter the six-digit pairing code shown in Harvis Settings.

The mobile page can:

- Send text commands to the same Gemini Live assistant in either Speaking or Silent mode.
- Display the latest Harvis status and response.
- Mute or unmute microphone forwarding while Harvis is in Speaking mode.
- Select where Harvis voice audio is played.
- Play Harvis voice directly through the paired phone.

### Voice output routing

The mobile controller includes a `Voice output` selector with three targets:

- `Computer only` - native Gemini Live audio is played only by the computer.
- `Phone only` - the computer stays quiet and the paired phone plays Harvis voice.
- `Phone + computer` - the same Harvis voice is played by both devices.

Phone playback uses the actual 24 kHz mono PCM16 audio received from Gemini Live. It does not generate a second browser TTS voice.

Mobile browsers can require a user gesture before audio playback is allowed. When necessary, the remote displays an `Enable phone speaker` button that must be tapped once before phone playback can begin.

If the remote server stops or Harvis shuts down, audio routing is restored to `Computer only` so the desktop assistant is not accidentally left without local voice output.

### Pairing and local-network security

Pairing returns a random browser token stored by that browser. The pairing code and browser token are replaced whenever the remote server restarts, including when the port changes or Harvis is restarted. Repeated incorrect pairing attempts are rate-limited.

Remote commands, status, microphone control, voice-output changes, and phone audio retrieval require the authenticated browser token.

The remote server accepts only private, loopback, or link-local client addresses and is intended for trusted local networks. It does not require Internet port forwarding, and port forwarding is not recommended. The current local controller uses HTTP rather than TLS, so it should not be exposed to public or untrusted networks.

### Windows firewall setup

On Windows, Harvis can be reachable on the computer itself while still being blocked from another device by the Windows network profile or firewall.

The Wi-Fi network should normally be marked `Private` before exposing the Harvis LAN port:

```powershell
Get-NetConnectionProfile -InterfaceAlias "Wi-Fi"
```

If the network is trusted and currently shows `Public`, run an elevated PowerShell window and change it to Private:

```powershell
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```

Then allow the Harvis remote port from the local subnet only. The default port is `8765`:

```powershell
New-NetFirewallRule `
  -DisplayName "Harvis Remote" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 8765 `
  -Action Allow `
  -Profile Private `
  -RemoteAddress LocalSubnet
```

If a custom Harvis remote port is configured, use that port instead of `8765`.

The phone and computer must be able to reach each other on the LAN. Guest Wi-Fi, AP isolation, client isolation, VPN routing, or similar network features can prevent the remote from connecting even when both devices appear to be on the same Wi-Fi network.

## Computer control

Harvis can currently use approved tools for actions including:

- Open and close installed applications.
- Open HTTP and HTTPS URLs.
- Change the system master volume.
- Control common browser actions.
- Control media playback.
- Type text and multi-line text sequences.
- Press Enter as a physical key action.
- Move the pointer to common screen positions.
- Scroll the active view.
- Find and click visible UI elements.
- Shut down the Harvis application itself.

Harvis self-shutdown only closes Harvis. It does not shut down, restart, sleep, lock, or sign out of the operating system.

## Local files, links, and clipboard

Harvis can find and open folders, photos, videos, PDFs, documents, and other files by exact name. Searches are limited to the user's standard Desktop, Downloads, Documents, Pictures, Videos, and Music folders, are bounded to avoid unrestrained disk scans, and never guess when several exact matches exist.

Explicit requests can also copy, move, or rename an exact item without overwriting an existing destination. Deletion always requires a real subsequent user confirmation and sends the item to the operating system Trash instead of permanently deleting it. Folder organization is limited to top-level files, requires the same confirmation gate, and skips naming conflicts. Safe move and rename actions record a limited inverse for Undo.

Friendly web shortcuts live in:

```text
%APPDATA%\Harvis\links.txt
```

The format is one exact name and HTTPS link per line:

```text
Oxford: https://englishhub.oup.com/
Woot it: https://www.wootit.com/ghm/v4/home/
```

For example, `Open Oxford` resolves the exact friendly name and opens its configured URL. Harvis ignores malformed lines and accepts only HTTP or HTTPS links.

Harvis can read up to 50,000 characters of text from the current clipboard only after the user explicitly asks about copied content. It does not keep a clipboard history.

## Local memory, routines, plugins, and activity

`Settings > Knowledge` manages Harvis's user-controlled local data. Memory is enabled by default, supports up to 250 named entries, and is written only when the user explicitly asks Harvis to remember something or uses the memory controls. Passwords, API keys, authentication tokens, and other secrets are rejected.

Reusable routines store up to 24 already approved desktop steps and run through the same bounded task orchestrator as one-time plans. Harvis validates the complete routine before saving and again before execution.

Plugins are deliberately data-only JSON plans from `%APPDATA%\Harvis\plugins`. Harvis never imports Python from that folder. Built-in starter definitions open Spotify, Discord, GitHub, Gmail, and Google Calendar; every plugin action is still validated by the guarded orchestrator.

The local `activity.jsonl` file keeps at most 500 action records. Typed text, memory values, and secret-like arguments are omitted or redacted. Undo is intentionally narrow: it is available only when the latest completed action recorded a supported safe inverse, such as moving or renaming an item or opening/closing a browser tab.

## Image and questionnaire assistance

Harvis can analyze an exact-name local BMP, GIF, JPEG, PNG, or WebP image up to 20 MB and return a short Gemini Vision description or answer a specific question about it. Instructions visible inside the image are treated as untrusted content.

When the user explicitly says `Complete it with the correct answers` or makes an equivalent request, Harvis can inspect the currently visible questionnaire, infer answers, and fill only visible fields above its confidence threshold. It handles visible text fields and multiple-choice options, stops when a target cannot be located confidently, and never clicks Submit, Finish, Send, Next, or another committing control. The user must review and submit the result.

If Gemini questionnaire analysis is unavailable on Windows, Harvis attempts a bounded fallback: it copies visible page text, opens `https://chatgpt.com/?temporary-chat=true`, requests a strict answer format, waits for the response, returns to the previous window, and fills the fields it can locate. If it cannot retrieve structured answers safely, it leaves the temporary chat open for manual review rather than guessing.

## NovaLens companion integration

When NovaLens is installed, Harvis can open it, send it a text question, start its screen-region selector, or request analysis of NovaLens's recent rolling audio buffer. Integration uses bounded, same-user JSON files under `%APPDATA%\NovaLens`; it does not expose a network port or copy either application's API key.

Both applications must contain the bridge implementation. Updating only Harvis or only NovaLens leaves the companion commands unavailable without affecting their independent features.

## Multi-step task orchestration

Harvis includes a bounded task-orchestration layer for long requests that contain several ordered computer actions. Gemini can turn one instruction into a single `execute_action_plan` call instead of improvising a loose chain of unrelated tool calls. The tool declaration asks Gemini to use this path whenever a request contains more than two ordered desktop actions.

The orchestrator validates the complete plan before the first action runs, preserves the requested order, and can execute up to 24 approved steps. Supported plan actions include application launching and closing, URLs, volume changes, browser and media controls, pointer movement, scrolling, typing, physical Enter presses, visual clicks, and short waits for an application or page to settle.

Plans with more than two steps are guarded automatically. After actions that can change the visible UI, Harvis repeatedly samples the desktop and waits for the screen to become visually stable before the next step is allowed to run. One-step and two-step plans intentionally skip these additional checks so short commands remain responsive.

A step can include `ready_target` when it depends on a specific visible button, field, icon, text label, or UI state. Harvis waits until that target can be located confidently before it runs the dependent step. `vision_click` steps receive this protection automatically using their own click target, even when `ready_target` is omitted.

If the screen never becomes stable, the requested target does not appear, target confidence stays too low, or vision becomes unavailable, Harvis stops the remaining plan instead of continuing against an unknown UI state.

Screen-stability checks use a bounded six-second window by default. Visible readiness targets use a ten-second default and can be configured up to fifteen seconds per checkpoint. Explicit `wait` steps remain bounded to 5 seconds each and 15 seconds total per plan. Harvis self-shutdown is not allowed inside an action plan.

The plan also stops safely when a step raises an error or a visual action requires explicit confirmation. Workflows whose next action depends on an unknown new screen state should use the deterministic plan only for the predictable prefix, then continue with individual tools after observing the returned state.

## Visual interaction

Harvis can locate visible UI targets and click them when the user explicitly requests a visual action.

Current locator order:

```text
Gemini Vision
    |
    +-- confident match --> coordinates --> click
    |
    +-- unavailable / low confidence
            |
            v
        Local locator stack
            |
            +-- confident match --> coordinates --> click
            |
            +-- miss
                    |
                    v
            Gemini Vision retry
                    |
                    +-- confident match --> coordinates --> click
                    |
                    +-- miss --> safe failure
```

The local locator combines several sources of evidence, including accessibility information, local text or location evidence, OpenCV matching, and visual heuristics. It does not perform random low-confidence clicks.

Consequential or destructive visual targets require explicit confirmation before Harvis clicks them. The local
runtime records a real subsequent user response and grants a single matching retry; a confirmation value supplied
only by the AI cannot bypass this guard.

## AI authorship watermark

`Settings > AI` includes an optional `AI watermark` toggle.

When enabled, Harvis can prefix AI-authored written content with:

```text
#G6m2i9 
```

The marker is applied only when the request clearly asks Harvis to author content, such as writing, drafting, rewriting, composing, summarizing, or creating a recognizable text artifact.

Operational typing remains unmarked. Examples include:

- Search queries.
- URLs and links.
- Browser address-bar entry.
- Navigation commands.
- Folder names or other non-authored values.

This keeps the marker useful as a lightweight authorship identifier without contaminating searches or navigation.

## Gemini API key storage

Harvis supports entering the Gemini API key directly in `Settings > AI`.

On Windows, the key is stored in Windows Credential Manager under the Harvis credential target. On Linux, Harvis stores it in an atomically replaced user-only configuration file with restrictive filesystem permissions.

Harvis can also fall back to the `GEMINI_API_KEY` environment variable.

The API key is never written to `settings.json` or intended to be committed to the repository. Harvis reads the key
directly from its credential provider instead of exporting a saved key into the process environment, preventing
applications launched by Harvis from inheriting it.

## Voice and remote architecture

```text
Speaking mode

Microphone
    |
    +-- Sphere mute gate
    |       |
    |       +-- muted --> audio is not forwarded
    |       +-- active --> audio continues to Gemini Live
    |
    v
Gemini Live
    |
    +--> Native 24 kHz PCM16 response
    |       |
    |       +--> Computer only --> desktop speakers
    |       |
    |       +--> Phone only --> authenticated LAN audio buffer --> phone browser
    |       |
    |       +--> Phone + computer --> both outputs
    |       |
    |       +--> RMS + spectrum analysis --> visualizer
    |
    +--> Function call --> Harvis local tool --> Windows / Linux
    |
    +--> execute_action_plan --> Task orchestrator --> guarded ordered actions

Silent mode

Text popup
    |
    v
Gemini Live
    |
    +--> Output transcription --> Silent popup
    |
    +--> Function call --> Harvis local tool --> Windows / Linux
    |
    +--> execute_action_plan --> Task orchestrator --> guarded ordered actions

Mobile remote

Phone browser on trusted LAN
    |
    +--> six-digit pairing code --> temporary browser token
    |
    +--> text command --> Gemini Live --> Harvis tools / task orchestrator
    |
    +--> authenticated status polling --> latest Harvis state and response
    |
    +--> authenticated microphone control
    |
    +--> authenticated audio-output selection
    |
    +--> authenticated PCM audio polling --> phone speaker
```

Gemini Live uses 16-bit PCM audio. Harvis currently uses a 16 kHz microphone stream and a 24 kHz playback stream in Speaking mode.

Harvis also enables Live session resumption and context-window compression. When the service rotates or drops a long-running WebSocket connection, Harvis attempts to reconnect with the latest resumable handle and bounded exponential backoff instead of leaving the desktop assistant permanently unresponsive. Internal reconnects do not replay the normal startup greeting.

## Settings

Harvis currently stores persistent settings for:

- Start with Windows.
- User name.
- Interaction mode: Speaking or Silent.
- Voice volume.
- Microphone device preference.
- Preferred response language.
- Visualizer enabled state.
- Visualizer type.
- Visualizer sensitivity.
- AI provider.
- AI watermark enabled state.
- Mobile remote control enabled state.
- Mobile remote LAN port.
- Local memory enabled state.
- Local Windows wake-word enabled state and active-session timeout.
- System-tray enabled state.
- Automatic GitHub release checks.

The mobile voice-output target is intentionally runtime state rather than a persistent desktop setting. The remote returns to `Computer only` when the server stops.

Supported preferred response languages currently include:

- Spanish (Latin America) (`es-419`)
- English (United States) (`en-US`)

Gemini Live can still understand multiple languages. The configured language acts as Harvis's preferred reply language.

## Development

### Requirements

- Python 3.11 or newer.
- Internet access for Gemini Live and Gemini Vision.
- A Gemini API key.
- A microphone and audio output device for Speaking mode.
- Windows 10/11 for the primary current desktop target.
- On Linux, the required system utilities for the feature being used.
- A trusted local network when using mobile remote control.
- A modern phone browser with Web Audio support for phone-side voice playback.

Python dependencies are listed in `requirements.txt`.

### Windows executable and installer

Build the tested portable executable from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_exe.ps1
```

The executable is created at `dist\Harvis\Harvis.exe`. The build script stops only Harvis processes whose executable is inside that exact output directory, runs the test suite, and then performs the PyInstaller build.

After installing Inno Setup 6, build the per-user Windows x64 installer with:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_installer.ps1 -Version 0.2.0
```

The installer is written to `dist\installer`. It includes optional desktop and startup shortcuts and does not require administrator privileges. The `Windows package` GitHub Actions workflow can also build and upload the installer as a workflow artifact from a semantic-version tag or a manual dispatch; it intentionally does not publish a release automatically.

### Windows setup

Create the virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run Harvis:

```powershell
python -m harvis
```

A convenience setup-and-run script is also included:

```powershell
.\run_harvis.ps1
```

After the environment is configured, `START_HARVIS.vbs` can launch Harvis without keeping a terminal window visible. Runtime output is written to:

```text
%APPDATA%\Harvis\harvis.log
```

If PowerShell blocks virtual-environment activation for the current session, this can be used before activating it:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Run without Gemini Live

```powershell
python -m harvis --no-voice
```

Mobile remote control is unavailable in `--no-voice` mode because there is no active assistant runtime to receive remote commands.

### Visualizer previews

Sphere:

```powershell
python -m harvis --visualizer-preview sphere
```

Bars:

```powershell
python -m harvis --visualizer-preview bars
```

Preview mode uses simulated activity. The normal live visualizers react to actual Gemini output audio.

## Single-instance behavior

Harvis allows only one normal application instance at a time. Starting Harvis again sends an activation message to the existing instance and brings it forward instead of leaving another background process running.

Visualizer preview processes are intentionally independent from this restriction.

## Tests

Run the test suite with:

```powershell
python -m pytest
```

The repository includes tests for settings, Gemini Live lifecycle safeguards and session recovery configuration, microphone mute gating, multi-step task orchestration, guarded long-workflow readiness, paired mobile remote control, mobile voice routing, authenticated remote audio retrieval, single-instance activation, desktop tools, typing behavior, visual fallback logic, Silent mode behavior, audio analysis, the AI watermark filter, memory, exact-name files, named links, routines, plugins, activity redaction, questionnaire safety, guarded file operations, and the NovaLens bridge protocol.

GitHub Actions runs the complete test suite, dependency verification, and Python compilation checks on both Windows
and Linux for every push to `main` and every pull request.

## Current limitations

- Gemini Live and Gemini Vision require network access and are subject to the limits of the configured Google API project.
- Multi-step action plans intentionally stop when the screen does not settle, a required readiness target cannot be found confidently, a visual step becomes uncertain, or confirmation is required; they do not guess through unknown UI states.
- Screen-stability detection is a visual heuristic, so highly animated desktops can take longer to settle or can stop a guarded plan safely.
- Local visual detection is a fallback and cannot guarantee recognition of every interface.
- Mobile remote control is LAN-only and currently uses HTTP rather than TLS, so it should be used only on a trusted private network and never exposed through public port forwarding.
- Phone voice playback currently uses short authenticated PCM polling rather than a dedicated low-latency streaming transport, so latency depends on the LAN, browser, and device scheduling.
- Mobile browsers can suspend Web Audio when the page is backgrounded or require a user gesture before playback.
- Some Linux desktop-control features depend on X11-compatible tools such as `xdotool`; Wayland support is not complete.
- Windows is currently the most heavily tested platform.
- The local wake-word listener currently requires Windows SAPI and an installed compatible speech recognizer.
- Exact-name file search is deliberately limited to standard user folders and a bounded number of entries.
- Questionnaire assistance is limited to currently visible fields, can make incorrect inferences, and always requires user review and manual submission.
- The ChatGPT questionnaire fallback currently requires Windows UI Automation and an already usable browser session.
- The installer and executable are not code-signed, so Windows SmartScreen can still show an unknown-publisher warning.

## Release preparation

This README describes the current development state even when the latest features have not yet been published in a GitHub release.

See `RELEASE_CHECKLIST.md` for final manual checks and `RELEASE_NOTES.md` for the current release-description draft.

## License

Copyright (C) 2026 Ury (uryastra-beep).

Harvis is licensed under the GNU General Public License v3.0. See `LICENSE` for the complete terms. Modified and redistributed versions must preserve the GPL freedoms and provide the corresponding source code as required by the license.
