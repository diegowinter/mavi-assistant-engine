import pyaudio
import numpy as np
import openwakeword.utils
from openwakeword.model import Model

from led_control import (
    turn_inactivity_led,
    turn_websocket_conn_led
)

openwakeword.utils.download_models()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

model_path = "o_la_ma_vee.tflite"
inference_framework = "tflite"

owwModel = Model(
    wakeword_models=[model_path],
    inference_framework=inference_framework
)


async def wait_wake_word(ser):
    audio = pyaudio.PyAudio()

    mic_stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    
    owwModel.reset()
    
    print("\n[INFO] Aguardando wake word...")

    has_activated_inactive = False
    
    while True:
        audio_data = np.frombuffer(mic_stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
        owwModel.predict(audio_data)

        for mdl in owwModel.prediction_buffer.keys():
            score = owwModel.prediction_buffer[mdl][-1]
            
            if score > 0 and not has_activated_inactive:
                await turn_inactivity_led(ser)
                has_activated_inactive = True
            
            # print(score)
            if score > 0.1:
                print("[INFO] ✅ Wake word detectada!")
                await turn_websocket_conn_led(ser)
                return