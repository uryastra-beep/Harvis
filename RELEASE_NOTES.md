# Harvis v1.0.0 Release Notes

Harvis v1.0.0 is the first public release of the Harvis desktop personal assistant. It combines Gemini Live conversation with guarded local computer control, visual interaction, local knowledge, reusable automation, and a paired mobile controller.

> Publication remains manual. Complete `RELEASE_CHECKLIST.md` before creating the GitHub release.

## Highlights

- Real-time Gemini Live native-audio conversation.
- Spanish (Latin America) and English response preferences.
- Automatic Gemini Live reconnection with session resumption, context-window compression, and bounded reconnect backoff.
- Speaking and Silent interaction modes.
- Guarded multi-step desktop workflows with screen-stability and visible-target readiness checks.
- Gemini Vision visual interaction with a local fallback and safe failure behavior.
- Local enforcement of confirmation for sensitive visual actions.
- Paired mobile remote control over a trusted local network.
- Harvis voice routing to the computer, the paired phone, or both devices.
- Local memory, named links, routines, JSON-only plugins, activity history, and limited safe Undo.
- Exact-name local file opening plus guarded copy, move, rename, Trash, and folder organization.
- Local image analysis and visible-questionnaire assistance without automatic submission.
- Optional local Windows wake-word activation.
- System-tray controls.
- PyInstaller portable Windows build and Inno Setup installer workflow.
- GNU GPLv3 licensing.

## Mobile remote control

`Settings > Advanced > Mobile remote control` can expose a responsive controller to phones and tablets on the same trusted local network.

The paired mobile page can:

- Send text commands to the active Gemini Live assistant in Speaking or Silent mode.
- Show the latest Harvis status and response transcript.
- Mute or unmute microphone forwarding while Speaking mode is active.
- Select the Harvis voice output target.

Voice output supports:

- `Computer only` - Harvis voice plays only through the desktop audio output.
- `Phone only` - the computer remains quiet and the paired phone plays Harvis voice.
- `Phone + computer` - the same Harvis response is played on both devices.

Phone playback uses the actual 24 kHz mono PCM16 audio returned by Gemini Live. It does not generate a separate browser text-to-speech voice. Mobile browsers can require a one-time user gesture before audio playback; the controller displays an `Enable phone speaker` action when needed.

Pairing uses a six-digit code and an ephemeral browser token. The pairing code and token are regenerated when the remote server restarts. Repeated incorrect pairing attempts are rate-limited. Remote commands, status, microphone control, audio-output changes, and phone audio retrieval all require authentication.

The remote is LAN-only and currently uses HTTP rather than TLS. Do not expose the remote-control port through public Internet port forwarding or use it on an untrusted network.

## Speaking and Silent modes

Speaking mode uses microphone input and Gemini Live native voice output. Harvis can display either the Sphere or Bars live visualizer. A short click on the Sphere toggles microphone forwarding without disconnecting Gemini Live, and a visible diagonal indicator appears while the microphone is muted.

While Harvis is processing a request or looking for a visual target, the Sphere can morph into a rotating loading indicator and return to its normal audio-reactive state when the task continues or completes.

Silent mode does not open microphone or speaker streams. It uses a compact always-on-top text command popup, and typed commands are treated as directly addressed to Harvis.

## Desktop control and guarded workflows

Harvis can perform approved local actions including application launch and close, browser controls, media controls, master volume changes, typing, physical Enter presses, pointer movement, scrolling, URL opening, and Harvis self-shutdown.

Long instructions can be converted into bounded action plans of up to 24 approved steps. Plans with more than two steps use additional visual readiness protection. Harvis can wait for the screen to stabilize and for a required visible target before continuing. Missing targets, low confidence, unavailable vision, unstable screens, tool errors, or confirmation-required actions stop the remaining workflow rather than allowing Harvis to continue blindly.

Harvis self-shutdown closes only Harvis. It never shuts down, restarts, sleeps, locks, or signs out of the operating system.

## Visual interaction

The visual target strategy is:

```text
Gemini Vision
    -> local locator fallback when Gemini is unavailable or uncertain
    -> final Gemini Vision retry if the local locator also misses
    -> safe failure when no confident target is found
```

Consequential or destructive visual targets require a real subsequent user confirmation. An AI-supplied confirmation argument cannot authorize the action by itself.

## Local knowledge, files, routines, and plugins

`Settings > Knowledge` provides user-controlled local memory and related automation features.

Harvis can store explicit non-secret memories and rejects password, API-key, token, and secret-like entries. Friendly named links can be stored in `links.txt`. Reusable routines execute through the same guarded task orchestrator used by one-time plans.

Plugins are declarative JSON plans loaded from the Harvis plugin directory. Harvis does not import or execute arbitrary Python plugin files.

Harvis keeps a bounded, redacted activity history. Typed text, memory values, and secret-like arguments are omitted or redacted. Undo is intentionally limited to actions that record a supported safe inverse.

## Local files and images

Harvis can find and open exact-name folders, photos, videos, PDFs, documents, and other files from standard user folders. Ambiguous exact-name matches are reported instead of guessed.

Explicit requests can copy, move, or rename items without overwriting existing destinations. Trash and folder organization use local confirmation gates, and deletion goes through the operating-system Trash rather than permanent deletion.

Harvis can also analyze supported exact-name local image files with Gemini Vision while treating instructions visible inside images as untrusted content.

## Questionnaire assistance

Harvis can inspect a visible questionnaire and fill confident visible answer fields when the user explicitly asks it to complete the questionnaire. It can handle visible text fields and multiple-choice targets while stopping safely when it cannot identify an answer or field with sufficient confidence.

Harvis does not automatically click `Submit`, `Finish`, `Send`, `Next`, or other committing controls. The user remains responsible for reviewing and submitting the completed questionnaire.

On Windows, a bounded temporary ChatGPT browser fallback is available when Gemini questionnaire analysis is unavailable. The fallback obtains structured answers and returns to the questionnaire while continuing to use Harvis's guarded local field locator.

## Local wake word and tray

On Windows, optional local wake-word mode can use Windows SAPI to recognize `Harvis` or `Jarvis` before opening the Gemini Live microphone session. After the configured active-session timeout, Harvis can return to local wake-word listening.

System-tray controls keep common actions available while the Settings window is hidden, including interaction mode, microphone state, Undo, and full exit.

## AI authorship watermark

When `Settings > AI > AI watermark` is enabled, Harvis can prefix AI-authored written content with:

```text
#G6m2i9 
```

The marker is intended for content Harvis is asked to author. Searches, URLs, navigation, and other operational typing remain unmarked.

## Credential handling

The Gemini API key can be configured from Harvis Settings.

On Windows, Harvis stores the saved key in Windows Credential Manager. On Linux, it uses a user-only secrets file with restrictive permissions. The key is not written to `settings.json`, and saved credentials are not intentionally exported into child-process environments.

## Windows packaging

The repository includes:

- `build\build_exe.ps1` for the portable PyInstaller build.
- `build\build_installer.ps1` for the final portable ZIP and Inno Setup installer.
- `.github\workflows\windows-package.yml` for a manually dispatched or tag-triggered package build that uploads both Windows artifacts.

The v1.0.0 Windows artifacts are expected to use these file names:

```text
Harvis-1.0.0-Windows-x64-portable.zip
Harvis-Setup-1.0.0-Windows-x64.exe
```

The executable and installer are not code-signed. Windows can therefore show an unknown-publisher or SmartScreen warning.

## Setup from source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m harvis
```

After setup, `START_HARVIS.vbs` can launch Harvis without leaving a terminal window visible.

## Platform status

Windows is the primary and most heavily tested target for v1.0.0. Linux support exists for several integrations, but some desktop-control features still depend on X11-compatible utilities and are not fully Wayland-ready.

## Important notes

- Gemini Live and Gemini Vision require network access and a configured Gemini API key.
- Cloud behavior is subject to the limits of the configured Google API project.
- Mobile remote control is intended only for trusted private networks.
- Screen-stability and visual-target checks are deliberately fail-safe and can stop workflows rather than guess.
- The Windows artifacts are currently unsigned.
- Harvis is licensed under GNU GPLv3; see `LICENSE`.

## Before publishing

Complete every applicable release gate in `RELEASE_CHECKLIST.md`, confirm the full test suite and Windows smoke tests, build the final portable ZIP and installer, and then create the manual GitHub release with tag `v1.0.0`.
