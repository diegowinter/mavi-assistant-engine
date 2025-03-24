import asyncio
import pyaudio
import numpy as np
import openwakeword.utils
from openwakeword.model import Model

openwakeword.utils.download_models()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

model_path = "o_la_ma_vee.onnx"
inference_framework = "onnx"

audio = pyaudio.PyAudio()
mic_stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

async def wait_wake_word():
    print("\n[INFO] Aguardando wake word...")

    owwModel = Model(
        wakeword_models=[model_path],
        inference_framework=inference_framework
    )

    while True:
        audio_data = np.frombuffer(mic_stream.read(CHUNK), dtype=np.int16)
        owwModel.predict(audio_data)

        for mdl in owwModel.prediction_buffer.keys():
            score = owwModel.prediction_buffer[mdl][-1]
            if score > 0.5:
                print("[INFO] ✅ Wake word detectada!")
                return

        await asyncio.sleep(0.01)
