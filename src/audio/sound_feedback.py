import simpleaudio as sa

def play_sound_feedback(effect):
    if effect == "wake":
        path = "wake.wav"
    elif effect == "timeout":
        path = "timeout.wav"
    
    wave_obj = sa.WaveObject.from_wave_file(path)
    play_obj = wave_obj.play()
    play_obj.wait_done()