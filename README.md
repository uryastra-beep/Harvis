# Harvis

Harvis is a Windows personal assistant designed to combine local system control, voice interaction, AI-powered answers, and optional audio-reactive visualizers.

## Project goals

Harvis is being built to:

- Execute local computer actions such as opening the default browser or changing system volume.
- Listen for voice requests and route them to the correct local action or AI provider.
- Speak responses through text-to-speech.
- Provide a dedicated settings interface.
- Offer optional audio-reactive visualizers, including a sphere and bar mode.

## Official color palette

- Primary: `#00072B`
- Secondary: `#85B1FF`
- Tertiary: `#53EEFC`

## Current development status

The repository currently contains:

- Persistent settings storage.
- A PySide6 settings interface with animated liquid-glass navigation.
- A structured intent model and action router.
- Windows system actions for opening URLs in the default browser and changing master volume.
- A real-time sphere visualizer using the secondary color for the outer structure and the tertiary color for the particle field.
- A real-time bar visualizer using the secondary color on the primary background.
- Audio-level and spectrum input hooks for the visualizers.
- Windows SAPI speech recognition using the system default microphone.
- Windows SAPI speech synthesis with configurable Harvis voice volume.
- Wake-word filtering for `Harvis` and `Jarvis`.
- Spoken command parsing for browser and master-volume commands.
- Automated tests for routing, settings persistence, and spoken command parsing.

AI provider integration and a dedicated low-power wake-word engine will be added in later development stages.

## Development

### Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- A Windows speech recognition engine and language profile compatible with the commands you intend to speak

### Setup

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

```powershell
python -m pip install -r requirements.txt
```

### Run settings and voice assistant

```powershell
python -m harvis
```

Harvis starts listening through the system default microphone when the normal settings application starts.

To start the settings application without voice recognition:

```powershell
python -m harvis --no-voice
```

### Current voice commands

The first voice-command parser is intentionally English-only so repository content remains fully English.

Examples:

```text
Harvis open Google
Harvis open YouTube
Harvis set volume to 70 percent
Jarvis set volume to seventy five percent
```

Commands that do not match a local action are routed to the AI intent. Until an AI provider is configured, Harvis answers that AI responses are not configured yet.

### Preview visualizers

Sphere:

```powershell
python -m harvis --visualizer-preview sphere
```

Bars:

```powershell
python -m harvis --visualizer-preview bars
```

The preview uses simulated audio motion until the live text-to-speech audio level is connected to the visualizer.

### Tests

```powershell
python -m pytest
```

## License

A project license has not been selected yet.
