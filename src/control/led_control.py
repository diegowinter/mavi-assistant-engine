import os
import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor
import serial

# Lê a variável de ambiente e normaliza pra boolean
LEDS_ENABLED = os.getenv("LEDS_ENABLED", "false").lower() in ("1", "true", "yes")

PORTA = "/dev/ttyUSB0"
BAUDRATE = 9600

stop_speaking_led = asyncio.Event()


def start_serial_communication_sync():
    """
    Inicializa a comunicação serial de forma síncrona.
    """
    if not LEDS_ENABLED:
        return None

    try:
        ser = serial.Serial(PORTA, BAUDRATE, timeout=1)
        time.sleep(2)  # Aguarda estabilização da porta
        return ser
    except serial.SerialException as e:
        print(f"[ERROR] Erro na comunicação serial: {e}")
        return None


async def start_serial_communication():
    """
    Inicializa a comunicação serial de forma assíncrona.
    """
    if not LEDS_ENABLED:
        return None

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        ser = await loop.run_in_executor(
            executor,
            start_serial_communication_sync
        )
    return ser


async def close_serial_communication(ser):
    """
    Fecha a comunicação serial.
    """
    if not LEDS_ENABLED or ser is None:
        return

    if ser.is_open:
        ser.close()
        print("[INFO] Comunicação serial encerrada.")


async def turn_listening_led(ser):
    """
    Acende LED verde para indicar que está escutando.
    """
    if not LEDS_ENABLED or ser is None:
        return

    ser.write(b'RESPIRAR:VERDE\n')
    print("[INFO] Sinal de microfone ativo (VERDE) enviado.")


async def turn_inactivity_led(ser):
    """
    Acende LED ciano para indicar inatividade.
    """
    if not LEDS_ENABLED or ser is None:
        return

    ser.write(b'CIANO:25\n')
    print("[INFO] Sinal de inatividade (CIANO) enviado.")


async def turn_thinking_led(ser):
    """
    Acende LED amarelo para indicar processamento.
    """
    if not LEDS_ENABLED or ser is None:
        return

    ser.write(b'RODAR:AMARELO:255\n')
    print("[INFO] Sinal de processamento (AMARELO) enviado.")


async def turn_websocket_conn_led(ser):
    """
    Acende LED azul para indicar conexão/desconexão de WebSocket.
    """
    if not LEDS_ENABLED or ser is None:
        return

    ser.write(b'AZUL:10\n')
    print("[INFO] Sinal de conexão/desconexão com o WebSocket (AZUL) enviado.")


async def turn_speaking_led(ser):
    """
    Pisca suavemente o LED ciano para indicar que está falando.
    """
    if not LEDS_ENABLED or ser is None:
        return

    current = random.randint(30, 200)
    while not stop_speaking_led.is_set():
        target = random.randint(30, 200)
        steps = 20
        delta = (target - current) / steps
        for _ in range(steps):
            current += delta
            ser.write(f"CIANO:{int(current)}\n".encode())
            await asyncio.sleep(0.05)
            if stop_speaking_led.is_set():
                break


async def start_led_task(ser):
    """
    Inicia a tarefa de piscar o LED de speaking.
    """
    if not LEDS_ENABLED or ser is None:
        return None

    stop_speaking_led.clear()
    return asyncio.create_task(turn_speaking_led(ser))


async def stop_led_task(ser):
    """
    Para a tarefa de piscar e retorna ao estado listening.
    """
    if not LEDS_ENABLED or ser is None:
        return

    stop_speaking_led.set()
    await turn_listening_led(ser)