# Harvis Release Notes Draft

> Replace the version placeholder below before publishing the GitHub release.

## Harvis vX.Y.Z

Harvis is a Python desktop personal assistant that combines Gemini Live conversation with approved local computer-control tools, visual interaction, configurable Speaking and Silent modes, and optional audio-reactive visualizers.

### Highlights

- Gemini Live native-audio conversation with Spanish (Latin America) and English response preferences.
- Speaking mode for microphone and voice interaction.
- Silent mode with a compact transparent text-command popup and no microphone or speaker streams.
- Secure Gemini API key storage from Settings.
- Single-instance startup behavior that reactivates the existing Harvis process.
- Local application discovery for opening and closing installed apps.
- Browser, media, system-volume, keyboard, mouse, scrolling, and Harvis self-shutdown tools.
- Visual clicking with Gemini Vision as the primary locator, a local fallback stack, and a final Gemini Vision retry.
- Confirmation requirement for sensitive or destructive visual actions.
- Live Sphere and Bars visualizers driven by Gemini output audio.
- Click the live Sphere to mute or unmute microphone forwarding without disconnecting Gemini Live.
- A visible diagonal indicator on the Sphere while the microphone is muted.
- Smooth Sphere-to-spinner transition while Harvis is processing a request or searching for a visual target.
- Optional `#G6m2i9` AI-authorship watermark for content Harvis is asked to write.
- Watermark intent filtering so searches, URLs, navigation, and other operational typing stay unmarked.
- Improved Unicode typing and explicit physical Enter handling.
- Cleaner Gemini Live startup, shutdown, and latency behavior.

### Sphere microphone control

In Speaking mode, a short click on the live Sphere toggles microphone forwarding. Harvis keeps the Gemini Live session connected and leaves the audio stream open, so unmuting is immediate.

Dragging the Sphere continues to reposition it without toggling the microphone. While muted, the Sphere displays a diagonal tertiary-color indicator.

### Sphere loading state

When Harvis starts processing a recognized request, the live Sphere smoothly shrinks and fades into a rotating multi-ring loading indicator using the Harvis secondary and tertiary colors. It returns to the normal audio-reactive Sphere when a response begins.

Visual target searches explicitly reactivate the loading state while the locator is working and return to the normal Sphere when the visual action succeeds, fails safely, or requires confirmation.

### AI watermark behavior

When `AI watermark` is enabled in Settings > AI, Harvis prefixes AI-authored content with:

```text
#G6m2i9 
```

The watermark is intended for written content that Harvis authors. It is not added to search queries, URLs, browser navigation, or similar operational text entry.

### Visual fallback behavior

Harvis currently uses this visual target strategy:

```text
Gemini Vision
    -> local locator fallback when Gemini is unavailable or uncertain
    -> final Gemini Vision retry if local detection also misses
    -> fail safely when no confident target is found
```

The local locator uses accessibility information and local visual evidence rather than random low-confidence clicking.

### Setup

Windows quick start:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m harvis
```

After setup, `START_HARVIS.vbs` can launch Harvis without leaving a terminal window visible.

### Important notes

- A Gemini API key is required for Gemini Live and Gemini Vision.
- Cloud features are subject to the limits of the configured Google API project.
- Windows is currently the most heavily tested platform.
- Linux support is present for several system integrations, but some desktop-control features still depend on X11-compatible tools and are not fully Wayland-ready.
- No packaged installer or signed executable is currently included.
- No project license has been selected yet.

### Before publishing

Complete the checks in `RELEASE_CHECKLIST.md`, choose the final version/tag, and edit this file if the release should mention additional known limitations or platform requirements.
