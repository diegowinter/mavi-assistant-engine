import asyncio
import json
import websockets
import asyncio.subprocess
import pyaudio

from led_control import (
    start_led_task,
    start_serial_communication,
    stop_led_task,
    turn_listening_led,
    turn_thinking_led
)
from utils import build_wav_header
from wake_word import wait_wake_word

# Eventos globais
capture_enabled = asyncio.Event()
capture_enabled.set()

restart_event = asyncio.Event()
start_timeout_event = asyncio.Event()
cancel_timeout_event = asyncio.Event()


async def timeout_handler(websocket, ser):
    print("[INFO] Iniciando timer de inatividade.")
    while True:
        await start_timeout_event.wait()
        start_timeout_event.clear()
        cancel_timeout_event.clear()

        try:
            await asyncio.wait_for(cancel_timeout_event.wait(), timeout=10)
            print("[INFO] Timeout cancelado a tempo.")
        except asyncio.TimeoutError:
            if capture_enabled.is_set():
                print("[TIMEOUT] Nenhuma atividade em 10s.")
                capture_enabled.clear()
                await turn_thinking_led(ser)
                await websocket.send(json.dumps({"type": "stop"}))
                restart_event.set()
                return


async def play_audio_round(websocket, ser):
    try:
        websocket_msg = await websocket.recv()
    except websockets.exceptions.ConnectionClosed:
        print("[INFO] WebSocket fechado — encerrando play_audio_round.")
        return False

    if not isinstance(websocket_msg, bytes):
        print("Mensagem recebida:", websocket_msg)
        transcription_msg = json.loads(websocket_msg)

        if "recognizing" in transcription_msg:
            cancel_timeout_event.set()

        if "recognized" in transcription_msg:
            print("[INFO] Parei de ouvir o microfone.")
            capture_enabled.clear()
            await turn_thinking_led(ser)
        return True

    # Inicia o ffplay para reproduzir o áudio desta rodada
    process = await asyncio.create_subprocess_exec(
        'ffplay', '-nodisp', '-autoexit', '-i', 'pipe:0', '-loglevel', 'quiet',
        stdin=asyncio.subprocess.PIPE
    )

    process.stdin.write(websocket_msg)
    await start_led_task(ser)
    await process.stdin.drain()

    while True:
        try:
            msg = await websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            print("[INFO] WebSocket fechado — encerrando reprodução.")
            break

        if isinstance(msg, bytes):
            process.stdin.write(msg)
            await process.stdin.drain()
        else:
            print("Rodada finalizada com detalhes:", msg)
            break

    process.stdin.close()
    await process.wait()

    capture_enabled.set()
    print("[INFO] Voltei a ouvir o microfone.")
    start_timeout_event.set()
    await stop_led_task(ser)
    return True


async def play_audio_stream(websocket, ser):
    while True:
        continuar = await play_audio_round(websocket, ser)
        if not continuar:
            break


async def send_audio_chunks(websocket):
    RATE = 44100
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    CHUNK = int(RATE * 0.1)
    BITS_PER_SAMPLE = 16

    audio_interface = pyaudio.PyAudio()
    stream = audio_interface.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    first_chunk = True

    try:
        while True:
            data = await asyncio.to_thread(stream.read, CHUNK, False)
            if not capture_enabled.is_set():
                continue

            # print("[INFO] Enviando áudio...")	
            if first_chunk:
                header = build_wav_header(CHANNELS, RATE, BITS_PER_SAMPLE)
                message = header + data
                first_chunk = False
            else:
                message = data

            await websocket.send(message)
    except websockets.exceptions.ConnectionClosed:
        print("[INFO] WebSocket fechado — send_audio_chunks encerrando.")
    except Exception as e:
        print("Erro ao enviar áudio:", e)
    finally:
        stream.stop_stream()
        stream.close()
        audio_interface.terminate()


async def text_to_speech_ws_streaming():
    restart_event.clear()
    
    ser = await start_serial_communication()
    if ser is None:
        print("[ERROR] Erro ao inicializar a comunicação serial.")
        return

    uri = (
        "wss://datalake-chat-dev.brazilsouth.cloudapp.azure.com"
        "/api-assistant/ws/conversation"
        "?doctor_id=205&language=pt-BR&output_format=mp3_44100"
    )

    await wait_wake_word()
    start_timeout_event.set()

    async with websockets.connect(uri) as websocket:
        print("[INFO] Conectado ao websocket.")
        capture_enabled.set()
        await turn_listening_led(ser)

        audio_send_task = asyncio.create_task(send_audio_chunks(websocket))
        audio_play_task = asyncio.create_task(play_audio_stream(websocket, ser))
        timeout_task = asyncio.create_task(timeout_handler(websocket, ser))

        done, pending = await asyncio.wait(
            [audio_send_task, audio_play_task, timeout_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        print("[INFO] Encerrando conexão com o websocket.")

        for task in pending:
            task.cancel()

    if restart_event.is_set():
        await text_to_speech_ws_streaming()


if __name__ == "__main__":
    asyncio.run(text_to_speech_ws_streaming())
