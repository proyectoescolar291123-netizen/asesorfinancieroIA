import os
import requests
from flask import Flask, request, make_response
from google import genai

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
TOKEN_VERIFICACION = "estudiante_ia_2026"
ACCESS_TOKEN = "EAANLEpqpXc0BQx9TPkHZBWbkGyu88I4Jdg68UZAUndbCiseBdOnQ560KlMHsVcZC389ThFqiHqbdkjZBkDf4g1HajE3z3MNikd7yIXY3jy8TP1yzkaWZARASAw3GkjB7n22GdvHlgVNjZANh4azd4xENZAZBqgivQLzvk7jQ03gt64WaOJaroPcwSRXfXlkGJYjjhjGpUsExOhmgnUn9JIuaAL8uYw9fJ6VEFPswDEofxKeSzr8RnAErt0ZAqZAGlcOCFScjrR0TlP5M7TaANF0ertNgZDZD"
PHONE_ID = "993609860504120"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Inicializamos el cliente con tu nueva clave
client = genai.Client(api_key=GEMINI_KEY)

def enviar_mensaje_whatsapp(texto, numero):
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }
    r = requests.post(url, headers=headers, json=data)
    return r.status_code

@app.route("/")
def index():
    return "Asesor Financiero EBC - Gemini 3 Activo", 200

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == TOKEN_VERIFICACION:
        return make_response(str(challenge), 200)
    return "Error de token", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    datos = request.get_json()
    try:
        if 'messages' in datos['entry'][0]['changes'][0]['value']:
            mensaje_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            numero_usuario = datos['entry'][0]['changes'][0]['value']['messages'][0]['from']

            # --- LÓGICA CON GEMINI 3 FLASH (NUEVA CUENTA) ---
            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=mensaje_usuario
                )
                texto_final = response.text
            except Exception as e:
                print(f"Error con Gemini 3: {e}")
                # Respaldo por si el preview está saturado
                try:
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=mensaje_usuario
                    )
                    texto_final = response.text
                except:
                    texto_final = "Hola! Soy tu asesor financiero. Mi sistema se está actualizando, ¿puedes repetir tu duda?"

            enviar_mensaje_whatsapp(texto_final, numero_usuario)
            
    except Exception as e:
        print(f"Error general: {e}")
        
    return make_response("EVENT_RECEIVED", 200)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
