import asyncio
import json
import websockets
import asyncio.subprocess
import pyaudio

from led_control import (
    start_led_task, start_serial_communication, stop_led_task, turn_listening_led, turn_thinking_led
)
from utils import build_wav_header

# Evento para controlar a captação: inicialmente, habilitado.
capture_enabled = asyncio.Event()
capture_enabled.set()

async def play_audio_round(websocket, ser):
    """
    Processa uma rodada de áudio:
    - Aguarda a primeira mensagem vinda do websocket.
    - Se for um chunk de áudio (bytes), desabilita a captação.
    - Enquanto receber chunks (bytes), envia para o ffplay.
    - Ao receber uma mensagem de texto (detalhes da rodada), encerra a rodada.
    - Após a reprodução, reabilita a captação.
    """
    try:
        # Aguarda a primeira mensagem da rodada
        websocket_msg = await websocket.recv()
    except websockets.exceptions.ConnectionClosed:
        return

    if not isinstance(websocket_msg, bytes):
        # Se a primeira mensagem for texto, não processa rodada e retorna
        print("Mensagem de detalhes recebida (sem reprodução):", websocket_msg)
        transcription_msg = json.loads(websocket_msg)
        if "recognized" in transcription_msg:
            print("[INFO] Parei de ouvir o microfone.")
            capture_enabled.clear()
            await turn_thinking_led(ser)
            # await turn_speaking_led(ser)
        return

    # Inicia o ffplay para reproduzir o áudio desta rodada
    process = await asyncio.create_subprocess_exec(
        'ffplay', '-nodisp', '-autoexit', '-i', 'pipe:0', '-loglevel', 'quiet',
        stdin=asyncio.subprocess.PIPE
    )
    

    # Envia o primeiro chunk recebido
    process.stdin.write(websocket_msg)
    await start_led_task(ser)
    await process.stdin.drain()

    # Continua lendo até receber uma mensagem de texto (detalhes da rodada)
    while True:
        try:
            msg = await websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            break
        if isinstance(msg, bytes):
            process.stdin.write(msg)
            await process.stdin.drain()
        else:
            print("Rodada finalizada com detalhes:", msg)
            break

    process.stdin.close()
    await process.wait()

    # Reabilita a captação após a rodada
    capture_enabled.set()
    print("[INFO] Voltei a ouvir o microfone.")
    await stop_led_task(ser)
    # await turn_listening_led(ser)


async def play_audio_stream(websocket, ser):
    """
    Processa continuamente rodadas de áudio.
    """
    while True:
        await play_audio_round(websocket, ser)


async def send_audio_chunks(websocket):
    """
    Captura áudio do microfone e envia chunks de 100ms.
    Enquanto a captação estiver desabilitada (durante a reprodução de uma
    rodada), os dados são lidos e descartados.
    Na primeira mensagem de cada rodada, envia o cabeçalho WAV.
    """
    RATE = 44100
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    CHUNK = int(RATE * 0.1)  # 100ms de áudio
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
            # Lê 100ms do áudio do microfone (em thread separada para não 
            # bloquear)
            data = await asyncio.to_thread(stream.read, CHUNK, False)
            if not capture_enabled.is_set():
                # Durante a reprodução, descarta os dados lidos para não 
                # acumular
                continue

            if first_chunk:
                header = build_wav_header(CHANNELS, RATE, BITS_PER_SAMPLE)
                message = header + data
                first_chunk = False
            else:
                message = data

            await websocket.send(message)
    except Exception as e:
        print("Erro ao enviar áudio:", e)
    finally:
        stream.stop_stream()
        stream.close()
        audio_interface.terminate()

async def text_to_speech_ws_streaming():
    """
    Conecta ao websocket, inicia a captação e a reprodução em rodadas.
    Enquanto uma rodada (áudio a ser reproduzido) estiver ativa, a captação é
    desabilitada; quando a rodada termina (ao receber a mensagem de detalhes),
    a captação é retomada.
    """
    # Inicializa a comunicação serial
    ser = await start_serial_communication()
    
    if (ser is None):
        print(
            "[ERROR] Erro ao inicializar a comunicação serial. A execução "
            "será interrompida."
        )
        return
    
    uri = (
        "wss://datalake-chat-dev.brazilsouth.cloudapp.azure.com"
        "/api-assistant/ws/conversation"
        "?doctor_id=205&language=pt-BR&output_format=mp3_44100"
    )
    
    async with websockets.connect(uri) as websocket:
        # Inicia duas tarefas em paralelo: envio do áudio e reprodução de 
        # rodadas
        await turn_listening_led(ser)
        
        audio_send_task = asyncio.create_task(send_audio_chunks(websocket))
        audio_play_task = asyncio.create_task(
            play_audio_stream(websocket, ser)
        )
        await asyncio.gather(audio_send_task, audio_play_task)

if __name__ == "__main__":
    asyncio.run(text_to_speech_ws_streaming())
