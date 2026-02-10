import re
from flask import Flask, render_template, request, jsonify
import os
import json
from dotenv import load_dotenv
from google.genai import Client

load_dotenv()

app = Flask(__name__)

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

@app.route("/procesar", methods=["POST"])
def procesar():
    texto = request.json.get("texto", "")
    
    idioma = detectar_idioma(texto)
    system_prompt = SYSTEM_PROMPT_ES if idioma == 'es' else SYSTEM_PROMPT_EN
    
    prompt = system_prompt + f"\nHumano dice: \"{texto}\"" if idioma == 'es' else system_prompt + f"\nHuman says: \"{texto}\""

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

        return jsonify({
            "mensaje": data.get("mensaje", "Hola… soy tu robot " if idioma == 'es' else "Hi... I'm your robot"),
            "gesto": data.get("gesto","lado"),
            "idioma": idioma
        })

    except Exception as e:
        return jsonify({
            "mensaje": "Ups… mi chip se confundió " if idioma == 'es' else "Oops... my chip got confused",
            "gesto": "triste",
            "idioma": idioma
        })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
