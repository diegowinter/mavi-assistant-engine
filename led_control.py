import asyncio
from concurrent.futures import ThreadPoolExecutor
import random
import time
import serial

PORTA = "/dev/ttyUSB0"
BAUDRATE = 9600

stop_speaking_led = asyncio.Event()


def start_serial_communication_sync():
    """
    Inicializa a comunicação serial de forma síncrona.
    """
    try:
        ser = serial.Serial(PORTA, BAUDRATE, timeout=1)
        time.sleep(2) # Aguarda a estabilização da comunicação serial
        return ser
    except serial.SerialException as e:
        print(f"[ERROR] Erro na comunicação serial: {e}")
        return None


async def start_serial_communication():
    """
    Inicializa a comunicação serial de forma assíncrona.
    """
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
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("[INFO] Comunicação serial encerrada.")


async def turn_listening_led(ser):
    verde = b'RESPIRAR:VERDE\n'
    ser.write(verde)
    print("[INFO] Sinal de microfone ativo (VERDE) enviado.")


async def turn_thinking_led(ser):
    vermelho = b'RODAR:VERMELHO:255\n'
    ser.write(vermelho)
    print("[INFO] Sinal de CARREGANDO (VERMELHO) enviado.")


async def turn_speaking_led(ser):
    """
    Envia um sinal para o LED de escuta, variando a intensidade aleatoriamente
    entre 0 e 255.
    """
    while not stop_speaking_led.is_set():
        intensity = random.randint(0, 255)
        command = f"AZUL:{intensity}\n".encode()
        ser.write(command)
        print(f"[INFO] Sinal de microfone ativo (AZUL:{intensity}) enviado.")
        await asyncio.sleep(0.3)  # Aguarda 300ms


async def start_led_task(ser):
    """
    Inicia a tarefa assíncrona de piscar o LED.
    """
    stop_speaking_led.clear()
    return asyncio.create_task(turn_speaking_led(ser))


async def stop_led_task(ser):
    """
    Para a execução da tarefa de piscar o LED.
    """
    stop_speaking_led.set()
    await turn_listening_led(ser)