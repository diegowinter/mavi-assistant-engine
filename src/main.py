import os
import asyncio
import json
import websockets
import pyaudio
from dotenv import load_dotenv
load_dotenv()

from .control.led_control import (
    start_led_task,
    start_serial_communication,
    stop_led_task,
    turn_websocket_conn_led,
    turn_listening_led,
    turn_thinking_led
)
from .audio.sound_feedback import play_sound_feedback
from .utils.audio_utils import build_wav_header
from .audio.wake_word import wait_wake_word


# Eventos globais
capture_enabled      = asyncio.Event(); capture_enabled.set()
restart_event        = asyncio.Event()
start_timeout_event  = asyncio.Event()
cancel_timeout_event = asyncio.Event()


SOUND_FEEDBACK_ENABLED = os.getenv("SOUND_FEEDBACK_ENABLED", "False").lower() == "true"


async def timeout_handler(websocket, ser):
    """
    Gerencia o timeout, parando a captura ao não receber nenhum evento 
    recognizing do servidor.
    """
    print("[INFO] Iniciando timer de inatividade.")
    while True:
        await start_timeout_event.wait()
        start_timeout_event.clear(); cancel_timeout_event.clear()
        try:
            await asyncio.wait_for(cancel_timeout_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            print("[TIMEOUT] Nenhuma atividade em 10s.")
            if SOUND_FEEDBACK_ENABLED:
                asyncio.create_task(asyncio.to_thread(play_sound_feedback, "timeout"))
            if capture_enabled.is_set():
                capture_enabled.clear()
                await turn_websocket_conn_led(ser)
                await websocket.send(json.dumps({"type": "stop"}))
                restart_event.set()
            return


async def send_audio_chunks(websocket):
    """
    Faz a captura a partir do microfone e envia os chunks para o websocket.
    Formato: PCM 16 bits, 44100 Hz, mono. O primeiro chunk é o header WAV, os
    demais são PCM.
    """
    RATE, CHANNELS = 44100, 1
    FORMAT = pyaudio.paInt16
    CHUNK  = int(RATE * 0.1)
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    first = True
    try:
        while True:
            data = await asyncio.to_thread(stream.read, CHUNK, False)
            if not capture_enabled.is_set():
                continue
            msg = (build_wav_header(CHANNELS, RATE, 16) + data) if first else data
            first = False
            await websocket.send(msg)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        stream.stop_stream(); stream.close(); pa.terminate()


async def websocket_receiver(websocket, audio_queue, ser):
    """
    Recebe as informações do websocket e direciona ou realiza ações de acordo
    com o tipo de mensagem. Se a mensagem for bytes, coloca na fila de áudio.
    Se for um JSON, verifica o tipo e executa a ação correspondente.
    """
    try:
        async for msg in websocket:
            if isinstance(msg, bytes):
                await audio_queue.put(msg)
            else:
                dj = json.loads(msg)
                print("[INFO] Mensagem recebida:", dj)
                if "recognizing" in dj:
                    cancel_timeout_event.set()
                if "recognized" in dj:
                    capture_enabled.clear()
                    print("[INFO] Parei de ouvir o microfone.")
                    await turn_thinking_led(ser)
                if "assistant_message" in dj:
                    await audio_queue.put(None)
    finally:
        await audio_queue.put(None)


async def audio_player(audio_queue, output_stream, ser, capacity_frames):
    """
    Toca cada chunk da fila. Quando recebe None, sinaliza fim da rodada e 
    volta a ouvir o microfone, mas continua vivo para tocar as próximas
    rodadas.
    """
    started = False
    while True:
        chunk = await audio_queue.get()
        if chunk is None:
            # Fim de uma rodada de áudio
            while output_stream.get_write_available() < capacity_frames:
                await asyncio.sleep(0.1)
            started = False
            capture_enabled.set()
            print("[INFO] Voltei a ouvir o microfone.")
            start_timeout_event.set()
            await stop_led_task(ser)
            # Volta a aguardar o próximo None ou chunks futuros
            continue

        # escreve sem bloquear o loop
        if not started:
            started = True
            await start_led_task(ser)
        await asyncio.to_thread(output_stream.write, chunk)


async def text_to_speech_ws_streaming():
    """
    Loop principal: conecta, roda tasks até restart_event, depois fecha 
    reinicia.
    """
    while True:
        restart_event.clear()
        ser = await start_serial_communication()

        pa = pyaudio.PyAudio()
        output_stream = pa.open(
            format=pyaudio.paInt16, channels=1,
            rate=44100, output=True,
            frames_per_buffer=int(44100 * 0.2)
        )
        
        # Captura a capacidade total de frames livres
        capacity = output_stream.get_write_available()

        await wait_wake_word(ser)
        if SOUND_FEEDBACK_ENABLED:
            asyncio.create_task(asyncio.to_thread(play_sound_feedback, "wake"))
        
        start_timeout_event.set()
        uri = (
            "wss://datalake-chat-dev.brazilsouth.cloudapp.azure.com"
            "/api/ws/conversation"
            "?doctor_id=205&language=pt-BR&output_format=pcm_44100"
        )
        async with websockets.connect(uri) as ws:
            print("[INFO] Conectado ao websocket.")
            capture_enabled.set()
            await turn_listening_led(ser)

            audio_queue  = asyncio.Queue()
            send_task    = asyncio.create_task(send_audio_chunks(ws))
            recv_task    = asyncio.create_task(websocket_receiver(ws, audio_queue, ser))
            play_task    = asyncio.create_task(audio_player(audio_queue, output_stream, ser, capacity))
            timeout_task = asyncio.create_task(timeout_handler(ws, ser))

            # espera sinal de timeout para reiniciar
            await restart_event.wait()

            # cancela tudo só após timeout
            for t in (send_task, recv_task, play_task, timeout_task):
                t.cancel()

        output_stream.close(); pa.terminate()
        if not restart_event.is_set():
            break


if __name__ == "__main__":
    asyncio.run(text_to_speech_ws_streaming())
