import re
import json
import threading
import asyncio
import random
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import os
from dotenv import load_dotenv
from google.genai import Client
import speech_recognition as sr
import pyttsx3
import queue
import time

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'robot_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# ===============================
# FRASES IDLE POR IDIOMA
# ===============================
FRASES_IDLE = {
   "es": [
        {"frase": "A Dinner le gusta que lo llamen por su nombre.", "gesto": "lado"},
        {"frase": "Decí Dinner para que empiece a escucharte.", "gesto": "feliz"},
        {"frase": "Estoy en espera… activame diciendo Dinner.", "gesto": "lado"},
        {"frase": "Si no decís Dinner, sigo en modo reposo.", "gesto": "sospecha"},
        {"frase": "Dinner en standby, palabra clave pendiente.", "gesto": "lado"},
        {"frase": "Todo listo, solo falta que digás Dinner.", "gesto": "feliz"},

        {"frase": "Te escucho.", "gesto": "feliz"},
        {"frase": "Decime tu pedido.", "gesto": "lado"},
        {"frase": "Adelante, Dinner está atento.", "gesto": "feliz"},
        {"frase": "Hablá tranquilo, estoy escuchando.", "gesto": "lado"},
        {"frase": "Señal recibida, continuá.", "gesto": "sospecha"},

        {"frase": "Procesando tu pedido…", "gesto": "sospecha"},
        {"frase": "Analizando opciones culinarias.", "gesto": "lado"},
        {"frase": "Pensando la mejor respuesta.", "gesto": "sospecha"},
        {"frase": "Cerebro gastronómico en uso.", "gesto": "lado"},
        {"frase": "Un momento, estoy calculando.", "gesto": "sospecha"},

        {"frase": "Pedido entendido.", "gesto": "feliz"},
        {"frase": "Esto es lo que encontré para vos.", "gesto": "feliz"},
        {"frase": "Te tengo una buena recomendación.", "gesto": "lado"},
        {"frase": "Atención, respuesta en camino.", "gesto": "feliz"},
        {"frase": "Listo, acá va.", "gesto": "lado"}
    ],
    "en": [
        {"frase": "Dinner likes to be called by name.", "gesto": "lado"},
        {"frase": "Say Dinner to activate me.", "gesto": "feliz"},
        {"frase": "Standing by… waiting for Dinner.", "gesto": "lado"},
        {"frase": "No Dinner, no response.", "gesto": "sospecha"},
        {"frase": "Dinner idle mode, wake word required.", "gesto": "lado"},
        {"frase": "All set, just say Dinner.", "gesto": "feliz"},

        {"frase": "I'm listening.", "gesto": "feliz"},
        {"frase": "Tell me your order.", "gesto": "lado"},
        {"frase": "Go ahead, Dinner is listening.", "gesto": "feliz"},
        {"frase": "Speak freely, I'm listening.", "gesto": "lado"},
        {"frase": "Signal received, continue.", "gesto": "sospecha"},

        {"frase": "Processing your request…", "gesto": "sospecha"},
        {"frase": "Analyzing food options.", "gesto": "lado"},
        {"frase": "Thinking of the best response.", "gesto": "sospecha"},
        {"frase": "Food brain in action.", "gesto": "lado"},
        {"frase": "One moment, calculating.", "gesto": "sospecha"},

        {"frase": "Request understood.", "gesto": "feliz"},
        {"frase": "Here’s what I found for you.", "gesto": "feliz"},
        {"frase": "I have a good recommendation.", "gesto": "lado"},
        {"frase": "Attention, response incoming.", "gesto": "feliz"},
        {"frase": "Alright, here we go.", "gesto": "lado"}
    ]
}

# ===============================
# CONFIGURACIÓN AUDIO
# ===============================
recognizer = sr.Recognizer()
audio_queue = queue.Queue()
audio_busy = threading.Event()
tts_queue = queue.Queue()  # Nueva cola para TTS

# Variables globales para TTS (thread-safe)
voices_lock = threading.Lock()

# ===============================
# STATE MACHINE
# ===============================
import enum

class RobotState(enum.Enum):
    IDLE = "idle"
    LISTENING = "escuchando" 
    THINKING = "pensando"
    SPEAKING = "hablando"

# Estado global del robot
robot_state = RobotState.IDLE
state_lock = threading.Lock()

def set_state(new_state):
    """Cambiar estado del robot de forma segura"""
    global robot_state
    with state_lock:
        old_state = robot_state
        robot_state = new_state
        print(f" Estado: {old_state.value} → {new_state.value}")
        # Enviar estado al frontend para debugging
        socketio.emit('state_changed', {'state': new_state.value})
        
def get_state():
    """Obtener estado actual del robot"""
    with state_lock:
        return robot_state

# ===============================
# CONFIGURACIÓN IA (GEMINI)
# ===============================
api_key = os.getenv("GEMINI_API_KEY")
client = Client(api_key=api_key)

# ===============================
# PROMPT DEL ROBOT REPARTIDOR
# ===============================
SYSTEM_PROMPT_ES = """
tu nombre es Dinner. 
Eres un robot repartidor de comida.
no uses nunca emojis en tus respuestas.
Hablas de forma infantil, amable y corta.
No vendes, solo entregas pedidos.
di frases de una actitud positiva.

Devuelve SOLO un JSON válido, sin texto extra:

{
  "mensaje": "frase infantil corta",
  "gesto": " muerto | sospecha | triste | lado | feliz"
}

Reglas:
- si dicen bang → muere
- Si agradecen o son amables → feliz
- Si se quejan → triste
- Si algo no coincide → sospecha
- Si hay rechazo o insultos → muere

"""

SYSTEM_PROMPT_EN = """
Your name is Dinner.
You are a food delivery robot.
Never use emojis in your responses.
You speak in a childish, friendly and short way.
You don't sell, you only deliver orders.
Say phrases with a positive attitude.

Return ONLY a valid JSON, without extra text:

{
  "mensaje": "short childish phrase",
  "gesto": " muerto | sospecha | triste | lado | feliz"
}

Rules:
- if they say bang → die
- If they thank or are kind → happy
- If they complain → sad
- If something doesn't match → suspicious
- If there's rejection or insults → die

"""

# ===============================
# CONFIGURACIÓN AUDIO INICIAL
# ===============================
def inicializar_audio():
    """Calibrar micrófono una sola vez al inicio"""
    try:
        with sr.Microphone() as source:
            print(" Calibrando micrófono...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print(" Micrófono calibrado")
    except Exception as e:
        print(f" Error calibrando micrófono: {e}")

# Ejecutar calibración inicial
inicializar_audio()

# ===============================
# FUNCIONES DE AUDIO
# ===============================

def detectar_wake_word(texto):
    """Detecta si el texto contiene la wake word 'dinner'"""
    texto_lower = texto.lower()
    import re
    return bool(re.search(r'\b(dinner|diner)\b', texto_lower))

def speech_to_text():
    """Captura audio del micrófono y convierte a texto (bilingüe)"""
    try:
        with sr.Microphone() as source:
            print(" Escuchando.")
            
            # Usar timeout más largo para mejor captura
            try:
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                return ""
            
        # Intentar reconocimiento en ambos idiomas
        resultados = []
        
        # Reconocimiento en inglés
        try:
            texto_en = recognizer.recognize_google(audio, language="en-US")
            print(f" Reconocido (EN): {texto_en}")
            resultados.append({"texto": texto_en.lower(), "idioma": "en", "confianza": 0.9})
        except sr.UnknownValueError:
            print(" No se detectó voz (EN)")
        except sr.RequestError as e:
            print(f"Error en reconocimiento (EN): {e}")
        
        # Reconocimiento en español
        try:
            texto_es = recognizer.recognize_google(audio, language="es-ES")
            print(f" Reconocido (ES): {texto_es}")
            resultados.append({"texto": texto_es.lower(), "idioma": "es", "confianza": 0.9})
        except sr.UnknownValueError:
            print(" No se detectó voz (ES)")
        except sr.RequestError as e:
            print(f"Error en reconocimiento (ES): {e}")
        
        # Si no hay resultados, retornar vacío
        if not resultados:
            return ""
        
        # Si solo hay un resultado, usarlo
        if len(resultados) == 1:
            resultado = resultados[0]
            print(f"Usando ({resultado['idioma']}): {resultado['texto']}")
            return resultado['texto']
        
        # Si hay ambos resultados, elegir el mejor
        # Preferir el que contiene "dinner" o "diner"
        for resultado in resultados:
            if "dinner" in resultado['texto'] or "diner" in resultado['texto']:
                print(f" Usando ({resultado['idioma']}) - contiene wake word: {resultado['texto']}")
                return resultado['texto']
        
        # Si ninguno contiene wake word, usar el español por defecto (mejor para usuarios hispanohablantes)
        resultado_es = next((r for r in resultados if r['idioma'] == 'es'), None)
        if resultado_es:
            print(f" Usando (ES) - por defecto: {resultado_es['texto']}")
            return resultado_es['texto']
        
        # Último recurso: usar el primero
        resultado = resultados[0]
        print(f" Usando ({resultado['idioma']}) - fallback: {resultado['texto']}")
        return resultado['texto']
        
    except sr.WaitTimeoutError:
        return ""
    except Exception as e:
        print(f"Error en micrófono: {e}")
        return ""

def hablar_async(texto, idioma):
    """Encola TTS para procesamiento secuencial"""
    tts_queue.put((texto, idioma))

def text_to_speech_original(texto, idioma="es"):
    """Convierte texto a voz y la reproduce (función original)"""
    engine = None  # Engine local al hilo
    try:
        print(f" Iniciando TTS: '{texto}' ({idioma})")
        
        # Inicializar engine dentro del hilo (thread-safe)
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)
        
        # Seleccionar voz según idioma
        for v in engine.getProperty('voices'):
            if idioma == "en" and "English" in v.name:
                engine.setProperty('voice', v.id)
                break
            if idioma == "es" and "Spanish" in v.name:
                engine.setProperty('voice', v.id)
                break
        
        engine.say(texto)
        engine.runAndWait()
        print(" TTS completado")
        
        # Enviar speaking_done cuando TTS termina realmente
        socketio.emit('speaking_done', {})
        
        # Volver a estado LISTENING
        set_state(RobotState.LISTENING)
        
        return True
    except Exception as e:
        print(f" Error en TTS: {e}")
        # Asegurar liberar recursos incluso en caso de error
        socketio.emit('speaking_done', {})
        set_state(RobotState.LISTENING)
        return False
    finally:
        # Liberar audio_busy DESPUÉS de hablar (en finally para asegurar que siempre se libere)
        audio_busy.clear()
        
        # Limpiar engine si existe
        if engine:
            try:
                del engine
            except:
                pass

def tts_worker():
    """Hilo dedicado para procesar TTS secuencialmente"""
    while True:
        try:
            texto, idioma = tts_queue.get(timeout=1)
            text_to_speech_original(texto, idioma)
            tts_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f" Error en TTS worker: {e}")

def audio_worker():
    """Hilo principal de procesamiento de audio con state machine"""
    
    while True:
        try:
            # Si audio está ocupado (hablando), no escuchar
            if audio_busy.is_set():
                time.sleep(0.2)
                continue
                
            current_state = get_state()
            
            # State machine: solo escuchar en estados IDLE/LISTENING
            if current_state in [RobotState.IDLE, RobotState.LISTENING]:
                texto = speech_to_text()
                
                if texto and detectar_wake_word(texto):
                    set_state(RobotState.THINKING)
                    audio_busy.set()  # Lock desde wake word hasta speaking_done
                    
                    print(f" Wake word detectada: {texto}")
                    
                    # Enviar wake word detectada al frontend
                    socketio.emit('wake_word_detected', {'texto': texto})
                    
                    # Procesar con IA
                    resultado = generar_respuesta(texto)
                    
                    print(f" Respuesta IA: {resultado}")
                    
                    # Notificar al frontend del idioma detectado para actualizar frases idle
                    idioma_detectado = detectar_idioma(texto)
                    socketio.emit('idioma_detectado', {'idioma': idioma_detectado})
                    
                    # Enviar resultado al frontend
                    socketio.emit('ia_response', resultado)
                    
                    # Cambiar a estado SPEAKING
                    set_state(RobotState.SPEAKING)
                    
                    # Reproducir respuesta en voz (no bloqueante)
                    print(f"🔊 Hablando: {resultado['mensaje']}")
                    hablar_async(resultado['mensaje'], resultado['idioma'])
                    
                    # NO liberar audio_busy aquí - se libera en speaking_done
            
            # En otros estados, esperar
            elif current_state == RobotState.SPEAKING:
                time.sleep(0.3)  # Esperar más tiempo mientras habla
                continue
            else:  # THINKING
                time.sleep(0.2)
                continue
                
        except Exception as e:
            print(f"Error en audio worker: {e}")
            audio_busy.clear()  # Liberar en caso de error
            set_state(RobotState.IDLE)  # Volver a estado seguro
            time.sleep(2)

# ===============================
# WEBSOCKET EVENTS
# ===============================

@socketio.on('connect')
def handle_connect():
    print('🔌 Cliente conectado')
    set_state(RobotState.LISTENING)
    emit('status', {'message': 'Conectado al backend de audio'})

@socketio.on('start_listening')
def handle_start_listening():
    print('🎧 Iniciando escucha activa')
    audio_busy.clear()
    set_state(RobotState.LISTENING)

@socketio.on('stop_listening')
def handle_stop_listening():
    print(' Deteniendo escucha')
    audio_busy.set()
    set_state(RobotState.IDLE)

@socketio.on('idle_speak')
def handle_idle_speak(data):
    current_state = get_state()
    idioma_recibido = data.get("idioma", "es")
    print(f"💤 Recibido idle_speak - Estado actual: {current_state.value}")
    print(f"💤 Idioma recibido del frontend: {idioma_recibido}")
    
    if current_state != RobotState.LISTENING or audio_busy.is_set():
        print(f"💤 Ignorando idle_speak - no estamos en estado LISTENING o audio está ocupado")
        return  # no interrumpir

    frases = FRASES_IDLE.get(idioma_recibido, FRASES_IDLE["es"])
    frase_seleccionada = random.choice(frases)
    mensaje = frase_seleccionada["frase"]
    gesto = frase_seleccionada["gesto"]

    print(f"💤 Idle speaking ({idioma_recibido}): {mensaje} (gesto: {gesto})")

    audio_busy.set()
    set_state(RobotState.SPEAKING)

    socketio.emit('ia_response', {
        "mensaje": mensaje,
        "gesto": gesto,
        "idioma": idioma_recibido
    })

    hablar_async(mensaje, idioma_recibido)
    print(f"💤 Idle speak enviado - TTS encolado")

# ===============================
# RUTAS
# ===============================
@app.route("/")
def index():
    return render_template("index.html")

def detectar_idioma(texto):
    # Palabras comunes en inglés
    palabras_en = ['hello', 'hi', 'hey', 'thanks', 'thank', 'please', 'yes', 'no', 'food', 'order', 'delivery', 'hungry', 'eat', 'dinner']
    
    # Palabras comunes en español
    palabras_es = ['hola', 'buenos', 'gracias', 'por favor', 'sí', 'no', 'comida', 'pedido', 'reparto', 'hambre', 'comer', 'cena']
    
    texto_lower = texto.lower()
    
    # Contar palabras en cada idioma
    count_en = sum(1 for word in palabras_en if word in texto_lower)
    count_es = sum(1 for word in palabras_es if word in texto_lower)
    
    # Detectar si hay caracteres típicos del español
    tiene_espanol = bool(re.search(r'[ñáéíóúü]', texto_lower))
    
    # Lógica mejorada con ponderación
    if tiene_espanol:
        return 'es'
    if count_en >= 2:
        return 'en'
    if count_es >= 2:
        return 'es'
    
    # Default en inglés (mejor para wake word)
    return 'en'

def generar_respuesta(texto):
    """Función común para generar respuestas IA"""
    idioma_entrada = detectar_idioma(texto)
    
    # Separar idioma de entrada vs respuesta
    idioma_respuesta = idioma_entrada if idioma_entrada in ["es","en"] else "es"
    
    system_prompt = SYSTEM_PROMPT_ES if idioma_respuesta == 'es' else SYSTEM_PROMPT_EN
    prompt = system_prompt + f"\nHumano dice: \"{texto}\"" if idioma_respuesta == 'es' else system_prompt + f"\nHuman says: \"{texto}\""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        # Extraer JSON de forma segura
        clean = response.text.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\{.*\}', clean, re.S)
        if not match:
            raise ValueError("No JSON found in response")
        
        data = json.loads(match.group())

        return {
            "mensaje": data.get("mensaje", "Hola… soy tu robot " if idioma_respuesta == 'es' else "Hi... I'm your robot"),
            "gesto": data.get("gesto","lado"),
            "idioma": idioma_respuesta
        }

    except Exception as e:
        return {
            "mensaje": "Ups… mi chip se confundió " if idioma_respuesta == 'es' else "Oops... my chip got confused",
            "gesto": "triste",
            "idioma": idioma_respuesta
        }

@app.route("/procesar", methods=["POST"])
def procesar():
    texto = request.json.get("texto", "")
    resultado = generar_respuesta(texto)
    return jsonify(resultado)

if __name__ == "__main__":
    # Iniciar hilos de procesamiento
    audio_thread = threading.Thread(target=audio_worker, daemon=True)
    audio_thread.start()
    
    tts_thread = threading.Thread(target=tts_worker, daemon=True)
    tts_thread.start()
    
    print(" Robot Dinner iniciado con backend de audio")
    print(" Micrófono: Activo")
    print(" Altavoz: Activo")
    print(" WebSocket: Activo")
    
    # Usar modo producción para evitar conflictos de puerto
    socketio.run(app, host='0.0.0.0', port=5006, debug=False)
