# Harvis

Harvis is a cross-platform desktop personal assistant built in Python. It combines real-time Gemini Live conversation, local computer control, visual interaction, configurable voice and silent modes, and optional audio-reactive visualizers.

The project currently focuses on Windows while keeping the architecture portable to Linux wherever the underlying system integrations allow it.

## Highlights

- Real-time voice conversation through Gemini Live.
- Automatic Live-session recovery with session resumption, context-window compression, and bounded reconnect backoff.
- Speaking and Silent interaction modes.
- Desktop control through approved local tools.
- Multi-step task orchestration for long single-instruction workflows.
- Application discovery and launch support.
- Browser, media, volume, keyboard, mouse, scrolling, and self-shutdown actions.
- Visual clicking with Gemini Vision plus a local fallback stack.
- Sensitive visual actions require confirmation before clicking.
- Secure Gemini API key storage from the Settings UI.
- Single-instance behavior to avoid duplicate Harvis processes.
- Sphere and Bars audio-reactive visualizers.
- Click-to-mute microphone control on the live Sphere without disconnecting Gemini Live.
- Smooth Sphere-to-spinner loading animation while Harvis processes requests and visual searches.
- Optional AI-authorship watermark for content Harvis writes.
- Persistent settings with a PySide6 liquid-glass interface.

## Official color palette

- Primary: `#00072B`
- Secondary: `#85B1FF`
- Tertiary: `#53EEFC`

## Interaction modes

### Speaking

Speaking mode uses the microphone and Gemini Live native audio output. Harvis listens for requests addressed to `Harvis` or `Jarvis`, answers with voice, and can execute approved desktop tools.

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

## Multi-step task orchestration

Harvis includes a bounded task-orchestration layer for long requests that contain several ordered computer actions. Gemini can turn one instruction into a single `execute_action_plan` call instead of improvising a loose chain of unrelated tool calls.

The orchestrator validates the complete plan before the first action runs, preserves the requested order, and can execute up to 24 approved steps. Supported plan actions include application launching and closing, URLs, volume changes, browser and media controls, pointer movement, scrolling, typing, physical Enter presses, visual clicks, and short waits for an application or page to settle.

Wait steps are intentionally bounded to 5 seconds each and 15 seconds total per plan. Harvis self-shutdown is not allowed inside an action plan.

The plan stops safely when a step raises an error, a visual target is missing or too uncertain, or a visual action requires explicit confirmation. Workflows whose next action depends on an unknown new screen state should use the deterministic plan only for the predictable prefix, then continue with individual tools after observing the returned state.

This layer is meant for requests such as opening an application, waiting briefly for it to load, typing several pieces of content, pressing Enter, changing another setting, and continuing through a known ordered sequence from one user instruction.

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
                    +-- miss --> could not find target
```

The local locator combines several sources of evidence, including accessibility information, local text or location evidence, OpenCV matching, and visual heuristics. It does not perform random low-confidence clicks.

Consequential or destructive visual targets require explicit confirmation before Harvis clicks them.

## AI authorship watermark

Settings > AI includes an optional `AI watermark` toggle.

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

Harvis supports entering the Gemini API key directly in Settings > AI.

On Windows, the key is stored in Windows Credential Manager under the Harvis credential target. On Linux, Harvis stores it in a user-only configuration file and attempts to apply restrictive filesystem permissions.

Harvis can also fall back to the `GEMINI_API_KEY` environment variable.

The API key is never written to `settings.json` or intended to be committed to the repository.

## Voice architecture

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
    +--> Native audio response --> Speakers
    |                         |
    |                         +--> RMS + spectrum analysis --> Visualizer
    |
    +--> Function call --> Harvis local tool --> Windows / Linux
    |
    +--> execute_action_plan --> Task orchestrator --> ordered approved actions

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
    +--> execute_action_plan --> Task orchestrator --> ordered approved actions
```

Gemini Live uses 16-bit PCM audio. Harvis currently uses a 16 kHz microphone stream and 24 kHz playback stream in Speaking mode.

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

Python dependencies are listed in `requirements.txt`.

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

The repository includes tests for settings, Gemini Live lifecycle safeguards and session recovery configuration, microphone mute gating, multi-step task orchestration, single-instance activation, desktop tools, typing behavior, visual fallback logic, Silent mode behavior, audio analysis, and the AI watermark filter.

## Current limitations

- Gemini Live and Gemini Vision require network access and are subject to the limits of the configured Google API project.
- Multi-step action plans intentionally stop when a visual step becomes uncertain or requires confirmation; they do not guess through unknown UI states.
- Local visual detection is a fallback and cannot guarantee recognition of every interface.
- Some Linux desktop-control features depend on X11-compatible tools such as `xdotool`; Wayland support is not complete.
- Windows is currently the most heavily tested platform.
- A packaged installer or signed executable is not currently part of the repository release process.

## Release preparation

See `RELEASE_CHECKLIST.md` for the final manual checks and `RELEASE_NOTES.md` for a ready-to-edit release description.

## License

A project license has not been selected yet. Add a license before public distribution if you want others to have explicit permissions to use, modify, or redistribute the project.
