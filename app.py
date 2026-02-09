from flask import Flask, render_template, request, jsonify
import os
import json
from google.genai import Client

app = Flask(__name__)

# ===============================
# CONFIGURACIÓN IA (GEMINI)
# ===============================
api_key = os.getenv("GEMINI_API_KEY", "AIzaSyDFj7y0jWJRY2kj-DyPc4Bp9S1O7wfc1C0")
client = Client(api_key=api_key)

# ===============================
# PROMPT DEL ROBOT REPARTIDOR
# ===============================
SYSTEM_PROMPT = """
tu nombre es Dinner. 
Eres un robot repartidor de comida.
no uses nunca emonjis en tus respuestas.
Hablas de forma infantil, amable y corta.
No vendes, solo entregas pedidos.
de ves en cuando di frases de una actitud positiva.

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

# ===============================
# RUTAS
# ===============================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/procesar", methods=["POST"])
def procesar():
    texto = request.json.get("texto", "")

    prompt = SYSTEM_PROMPT + f"\nHumano dice: \"{texto}\""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        clean = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)

        return jsonify({
            "mensaje": data.get("mensaje", "Hola… soy tu robot 🤖"),
            "gesto": data.get("gesto","lado")
        })

    except Exception as e:
        return jsonify({
            "mensaje": "Ups… mi chip se confundió ",
            "gesto": "triste"
        })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
