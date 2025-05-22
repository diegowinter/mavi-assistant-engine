import simpleaudio as sa
from pathlib import Path

def play_sound_feedback(effect: str):
    """
    Toca o áudio 'wake.wav' ou 'timeout.wav' da pasta sounds/.
    """
    base_dir = Path(__file__).resolve().parents[2]

    sounds_dir = base_dir / "assets" / "sounds"

    if effect == "wake":
        sound_file = sounds_dir / "wake.wav"
    elif effect == "timeout":
        sound_file = sounds_dir / "timeout.wav"
    else:
        raise ValueError(f"Effect desconhecido: {effect}")

    wave_obj = sa.WaveObject.from_wave_file(str(sound_file))
    play_obj = wave_obj.play()
    play_obj.wait_done()