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

The repository currently contains the first Python foundation:

- Persistent settings storage.
- A PySide6 settings interface.
- A structured intent model and action router.
- Windows system actions for opening a URL in the default browser and changing master volume.
- Automated tests for the core router and settings persistence.

Voice recognition, wake-word detection, text-to-speech, AI provider integration, and audio-reactive visualizers will be added in later development stages.

## Development

### Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer

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

### Run

```powershell
python -m harvis
```

### Tests

```powershell
python -m pytest
```

## License

A project license has not been selected yet.
