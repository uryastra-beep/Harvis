import math
from array import array

from harvis.voice.gemini_live import OUTPUT_SAMPLE_RATE, SPECTRUM_BINS, GeminiLiveVoice


def _pcm16_sine(frequency: float, duration_seconds: float, amplitude: float = 0.5) -> bytes:
    sample_count = int(OUTPUT_SAMPLE_RATE * duration_seconds)
    samples = array(
        "h",
        (
            int(
                32767
                * amplitude
                * math.sin(math.tau * frequency * index / OUTPUT_SAMPLE_RATE)
            )
            for index in range(sample_count)
        ),
    )
    return samples.tobytes()


def test_audio_analysis_returns_silence_for_empty_audio() -> None:
    level, spectrum = GeminiLiveVoice._analyze_pcm16(b"")

    assert level == 0.0
    assert spectrum == [0.0 for _ in range(SPECTRUM_BINS)]


def test_audio_analysis_detects_voice_level_and_spectrum() -> None:
    level, spectrum = GeminiLiveVoice._analyze_pcm16(
        _pcm16_sine(440.0, 0.1)
    )

    assert 0.0 < level <= 1.0
    assert len(spectrum) == SPECTRUM_BINS
    assert max(spectrum) > 0.0
    assert all(0.0 <= value <= 1.0 for value in spectrum)
