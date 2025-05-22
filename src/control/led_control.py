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
    

async def turn_inactivity_led(ser):
    ciano = b'CIANO:25\n'
    ser.write(ciano)
    print("[INFO] Sinal de inatividade (CIANO) enviado.")
    

async def turn_thinking_led(ser):
    amarelo = b'RODAR:AMARELO:255\n'
    ser.write(amarelo)
    print("[INFO] Sinal de processamento (AMARELO) enviado.")


async def turn_websocket_conn_led(ser):
    azul = b'AZUL:10\n'
    ser.write(azul)
    print("[INFO] Sinal de conexão/desconexão com o WebSocket (AZUL) enviado.")
    

async def turn_speaking_led(ser):
    import random
    current = random.randint(30, 200)
    while not stop_speaking_led.is_set():
        target = random.randint(30, 200)
        steps = 20
        delta = (target - current) / steps
        for _ in range(steps):
            current += delta
            command = f"CIANO:{int(current)}\n".encode()
            ser.write(command)
            await asyncio.sleep(0.05)
            if stop_speaking_led.is_set():
                break
    

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
    
