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
- Windows system actions for opening a URL in the default browser and changing master volume.
- A real-time sphere visualizer using the secondary color for the outer structure and the tertiary color for the particle field.
- A real-time bar visualizer using the secondary color on the primary background.
- Audio-level and spectrum input hooks so the visualizers can be connected to Harvis voice output later.
- Automated tests for the core router and settings persistence.

Voice recognition, wake-word detection, text-to-speech, and AI provider integration will be added in later development stages.

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

### Run settings

```powershell
python -m harvis
```

### Preview visualizers

Sphere:

```powershell
python -m harvis --visualizer-preview sphere
```

Bars:

```powershell
python -m harvis --visualizer-preview bars
```

The preview uses simulated audio motion until the text-to-speech pipeline is connected.

### Tests

```powershell
python -m pytest
```

## License

A project license has not been selected yet.
