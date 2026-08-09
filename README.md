# Harvis

Harvis is a desktop personal assistant designed to combine local system control, real-time voice interaction, AI-powered answers, and optional audio-reactive visualizers.

## Project goals

Harvis is being built to:

- Execute local computer actions such as opening the default browser or changing system volume.
- Use the same voice architecture on Windows and Linux.
- Hold low-latency voice conversations through Gemini Live.
- Provide a dedicated settings interface.
- Offer optional audio-reactive visualizers, including sphere and bar modes.

## Official color palette

- Primary: `#00072B`
- Secondary: `#85B1FF`
- Tertiary: `#53EEFC`

## Current development status

The repository currently contains:

- Persistent settings storage.
- A PySide6 settings interface with animated liquid-glass navigation.
- Gemini Live native audio input and output.
- Input and output transcription in the development console.
- Gemini Live function calling for approved local actions.
- Local tools for opening HTTP/HTTPS URLs and changing master volume.
- Windows master-volume support through pycaw.
- Linux master-volume support through `wpctl` or `pactl`.
- Preferred language settings for Spanish (Latin America) and English (United States).
- A live sphere visualizer driven by the actual Gemini output amplitude.
- A live bar visualizer driven by real-time frequency analysis of Gemini output PCM audio.
- Automated tests for routing, settings persistence, the legacy spoken-command parser, and Gemini audio analysis.

The current Gemini Live prototype streams microphone audio while Harvis is running. The model is instructed to respond or use tools only when addressed as `Harvis` or `Jarvis`. A dedicated local low-power wake-word engine will be added later so idle audio does not need to be sent to the cloud.

## Voice architecture

```text
Microphone
    |
    v
Gemini Live
    |
    +--> Native audio response --> Speakers
    |                         |
    |                         +--> RMS + spectrum analysis --> Live visualizer
    |
    +--> Function call --> Harvis local tool --> Windows / Linux
```

Gemini Live uses 16-bit PCM microphone input and returns 16-bit PCM audio output. Harvis currently uses a 16 kHz microphone stream and 24 kHz playback stream.

## Development

### Requirements

- Python 3.11 or newer
- A working microphone and audio output device
- Internet access for Gemini Live
- A Gemini API key
- Windows 10/11 for the current Windows UI target
- On Linux, PortAudio plus either PipeWire (`wpctl`) or PulseAudio (`pactl`) for the relevant audio/system features

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

### Gemini API key

Harvis reads the Gemini key from the `GEMINI_API_KEY` environment variable. Never commit an API key to this repository.

For the current PowerShell session:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
```

To save it for the current Windows user:

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "YOUR_KEY", "User")
```

Open a new terminal after setting a persistent user environment variable.

### Run settings and Gemini Live

```powershell
python -m harvis
```

Expected development console status:

```text
[Harvis] Gemini Live runtime scheduled to start.
[Harvis] Starting Gemini Live voice assistant
[Harvis] Connecting to Gemini Live
[Harvis] Gemini Live connected
[Harvis] Listening with Gemini Live (es-419)
```

Input and output transcripts are printed as:

```text
[Harvis] Heard: ...
[Harvis] Response: ...
```

Try:

```text
Harvis, abre Google.
Harvis, pon el volumen al 70 por ciento.
Harvis, what is the capital of Japan?
```

The first two requests can use local tools. General questions are answered directly by Gemini Live.

To start the settings application without Gemini Live:

```powershell
python -m harvis --no-voice
```

## Settings

### Language

The language setting controls Harvis's preferred response language:

- Spanish (Latin America) (`es-419`)
- English (United States) (`en-US`)

Gemini Live can still understand multiple languages. Native audio models choose the spoken language automatically; Harvis uses the setting as a response preference through its system instruction.

### AI

The active provider is `Gemini Live`. The API key is read from `GEMINI_API_KEY` and is not written to Harvis settings.

### Visualizer

When `Enable visualizer` is active, Harvis opens the selected live visualizer with the normal application. The sphere reacts to the actual output amplitude and the bars use a 42-bin real-time frequency analysis of the Gemini voice PCM stream. Sensitivity and visualizer type are applied from Settings.

The separate preview button and preview CLI commands remain available and use simulated motion so the visualizer can be inspected without a live Gemini response.

Sphere preview:

```powershell
python -m harvis --visualizer-preview sphere
```

Bars preview:

```powershell
python -m harvis --visualizer-preview bars
```

## Tests

```powershell
python -m pytest
```

## License

A project license has not been selected yet.
